# Table Of Contents

- [Introduction](#introduction)
- [How-To](#howto)

# Introduction <a name="introduction" />

The current [Slack Channel Connector for Rasa][rasa slack channel] requires
a public (HTTP/HTTPS) endpoint to receive messages via a webhook. This means
you either have to run your Rasa bot in public cloud, use tunneling mechanism
such as [ngrok][ngrok], or configure your firewall to expose a public endpoint.
But if these scenarios are stricted prohibited by your security policy then
the only viable option would be to use [Slack Socket Mode][slack socket mode],
and live with it's limitations (i.e. can't list the app in public
Slack App Directory).

Rasa currently does not support [Slack Socket Mode][slack socket mode]
out-of-the-box.

This repo contains a sample [Rasa custom connector][rasa custom connector]
for Slack using [Slack Socket Mode][slack socket mode].

---
**NOTE:**

This is demo code showing how Rasa Slack connector using socket mode can be
done. Currently it only handles the Slack `app_mention` event for demo
purposes. See https://api.slack.com/events for a complete list of Slack
events.
---


# How-To <a name="howto" />

To use the Slack socket mode connector:

1. git clone this repo to the server where you are deploying Rasa bot. If you
   are running Rasa in a container, make sure this repo is on a volume that
   is accessible by the container.

2. install Python `slack_bolt` package and make sure it's on the PYTHONPATH.
   If you are running Rasa in a container, make sure the `slack_bot` and it's
   dependent packages are installed on a volume that is accessible by the
   container. For example:

```console
pip install --target=/path/to/my/rasabot/volume/slack_bolt slack_bolt
```

3. follow the [Slack Creating An App][slack creating an app] instructions
   to create an app for your Rasa bot. Note down the bot token. It should
   begin with `xoxb-`.

4. follow the [Slack App Setup][slack app setup] instructions to create
   an app token. Note down the app token. It should begin with `xapp-`.

5. create a file with the name `credentials.yml` in your Rasa root directory,
   which contains the Python path to the Slack socket mode connector, along
   with the `slack_bot_token` and `slack_app_token` obtained from above.
   For example, your `credentials.yml` content should looks like this.

```
custom_connectors.slack_socketmode.SlackSocketModeInput:
  slack_bot_token: "xoxb-123456789012-123456789012-dF668EJ1i5twtTKt394cUmxz"
  slack_app_token: "xapp-3-BC2A68K9T8T-123456789012-123d264c9f5c123456e3ec782ba8193868231123385da5bbb8c59d37ee123456k"
```

Here's a sample Docker Compose file showing how to use the Slack socket mode
connector.

```
version: '3.1'

services:

  rasa_bot:
    image: rasa/rasa:2.8.26
    user: "${UID}:${GID}"
    volumes:
      - "/rasa_bot:/app"
    command:
      - run
      - --enable-api
    ports:
      - "5005:5005"
    environment:
      - PYTHONPATH=$PYTHONPATH:/app/slack_bolt:/app/rasa_slack_socketmode_demo
```

In this example, this repo (`rasa_slack_socketmode_demo`) is cloned into
`/rasa_bot` directory and the `slack_bolt` packages are installed into
`/rasa_bot/slack_bolt/`.

And the `/rasa_bot` directory content should looks like this:

```
actions		 data		models			    tests
config.yml	 domain.yml	rasa_slack_socketmode_demo
credentials.yml  endpoints.yml	slack_bolt
```


[ngrok]: https://ngrok.com/
[rasa custom connector]: https://rasa.com/docs/rasa/connectors/custom-connectors/
[rasa slack channel]: https://rasa.com/docs/rasa/connectors/slack
[slack app setup]: https://api.slack.com/apis/connections/socket#setup
[slack socket mode]: https://api.slack.com/apis/connections/socket
