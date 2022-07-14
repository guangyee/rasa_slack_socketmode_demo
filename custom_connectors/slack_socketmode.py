# Copyright (c) 2022 SUSE LLC
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 3 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.   See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, contact SUSE LLC.
#
# To contact SUSE about this file by physical or electronic mail,
# you may find current contact information at www.suse.com


############################################################################
# A custom connector which utilizing Slack socket mode to communicate      #
# with Slack via Events API, avoiding the need to expose a public          #
# endpoint.                                                                #
#                                                                          #
# NOTE: this is merely sample code showing how Rasa Slack channel          #
# with socket mode can be done. It only implemented the Slack app_mention  #
# event for demo purposes.                                                 #
############################################################################

import logging
import re
from typing import (
     Any,
     Awaitable,
     Callable,
     Dict,
     List,
     Optional,
     Text
)

import rasa.core.channels.channel
from rasa.core.channels.channel import (
    InputChannel,
    OutputChannel,
    UserMessage,
)

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.context.say.async_say import AsyncSay
from sanic import Blueprint, Sanic, response
from sanic.request import Request
from sanic.response import HTTPResponse


class SlackSocketModeOutput(OutputChannel):
    """Slack output channel using socket mode"""

    @classmethod
    def name(cls) -> Text:
        return "slack_socketmode"

    def __init__(
        self,
        event: Dict[Text, Any],
        say: AsyncSay
    ) -> None:
        self.event = event
        self.say = say

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        channel = self.event.get('channel', recipient_id)
        for message_part in text.strip().split("\n\n"):
            await self.say(
                channel=channel, as_user=True, text=message_part, type="mrkdwn"
            )

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        channel = self.event.get('channel', recipient_id)
        image_block = {"type": "image", "image_url": image, "alt_text": image}

        await self.say(
            channel=channel, as_user=True, text=image, blocks=[image_block]
        )

    async def send_attachment(
        self, recipient_id: Text, attachment: Dict[Text, Any], **kwargs: Any
    ) -> None:
        channel = self.event.get('channel', recipient_id)
        await self.say(
            channel=channel, as_user=True, attachments=[attachment], **kwargs
        )

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        channel = self.event.get('channel', recipient_id)
        text_block = {"type": "section",
                      "text": {"type": "plain_text", "text": text}}

        if len(buttons) > 5:
            rasa.shared.utils.io.raise_warning(
                "Slack API currently allows only up to 5 buttons. "
                "Since you added more than 5, slack will ignore all of them."
            )
            return await self.send_text_message(channel, text, **kwargs)

        button_block = {"type": "actions", "elements": []}
        for button in buttons:
            button_block["elements"].append(
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": button["title"]},
                    "value": button["payload"],
                }
            )

        await self.say(
            channel=channel,
            as_user=True,
            text=text,
            blocks=[text_block, button_block],
        )

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any],
        **kwargs: Any
    ) -> None:
        channel = json_message.get("channel", self.event.get('channel',
                                   recipient_id))
        json_message.setdefault("as_user", True)
        await self.say(channel=channel, **json_message)


class SlackSocketModeInput(InputChannel):
    """Slack input channel using socket mode."""

    @classmethod
    def name(cls) -> Text:
        return "slack_socketmode"

    @classmethod
    def from_credentials(
        cls, credentials: Optional[Dict[Text, Any]]
    ) -> InputChannel:
        if not credentials:
            cls.raise_missing_credentials_exception()

        return cls(
            credentials.get("slack_bot_token"),
            credentials.get("slack_app_token"),
        )

    def __init__(
        self,
        slack_bot_token: Text,
        slack_app_token: Text,
    ) -> None:
        """Create a Slack input channel."""
        self.slack_bot_token = slack_bot_token
        self.slack_app_token = slack_app_token

    @staticmethod
    def _sanitize_user_message(
        text: Text, uids_to_remove: Optional[List[Text]]
    ) -> Text:
        """Remove superfluous/wrong/problematic tokens from a message.

        Probably a good starting point for pre-formatting of user-provided text
        to make NLU's life easier in case they go funky to the power of extreme

        In the current state will just drop self-mentions of bot itself

        Args:
            text: raw message as sent from slack
            uids_to_remove: a list of user ids to remove from the content

        Returns:
            str: parsed and cleaned version of the input text
        """

        uids_to_remove = uids_to_remove or []

        for uid_to_remove in uids_to_remove:
            # heuristic to format majority cases OK
            # can be adjusted to taste later if needed,
            # but is a good first approximation
            for regex, replacement in [
                (fr"<@{uid_to_remove}>\s", ""),
                (fr"\s<@{uid_to_remove}>", ""),  # a bit arbitrary but
                                                 # probably OK
                (fr"<@{uid_to_remove}>", " "),
            ]:
                text = re.sub(regex, replacement, text)

        # Find multiple mailto or http links like
        # <mailto:xyz@rasa.com|xyz@rasa.com> or
        # <http://url.com|url.com> in text and substitute
        # it with original content
        pattern = r"(\<(?:mailto|http|https):\/\/.*?\|.*?\>)"
        match = re.findall(pattern, text)

        if match:
            for remove in match:
                replacement = remove.split("|")[1]
                replacement = replacement.replace(">", "")
                text = text.replace(remove, replacement)
        return text.strip()

    def get_metadata(self, event: Dict[Text, Any]) -> Dict[Text, Any]:
        return {
            "out_channel": event.get("channel"),
            "thread_id": event.get("thread_ts", event.get("ts")),
            "users": [],
        }

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        app = AsyncApp(token=self.slack_bot_token)
        socket_webhook = Blueprint('slack_socketmode')

        @socket_webhook.listener("before_server_start")
        async def before_server_start(api, loop):
            handler = AsyncSocketModeHandler(app, self.slack_app_token)
            await handler.connect_async()

        @socket_webhook.route("/", methods=["GET"])
        async def health(_: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @app.event('app_mention')
        async def handle_app_mention(event, say):
            text = self._sanitize_user_message(event["text"], [])
            user_msg = UserMessage(
                text,
                SlackSocketModeOutput(event, say),
                event.get("user", ""),
                input_channel=self.name(),
                metadata=self.get_metadata(event),
            )
            await on_new_message(user_msg)

        @app.event("message")
        async def handle_message_events(body, say, logger):
            logger.info(body)

        # TODO(gyee): need to handle additional events listed here
        # https://api.slack.com/events
        #
        # For example:
        #
        # @app.event("im_created")
        # async def handle_im_created_events(event, say):
        #     await say(":wave: What can I do for ya?")
        #
        # Also see https://slack.dev/bolt-python/tutorial/getting-started
        # on how to use slack_bolt Python APIs.

        return socket_webhook
