from django import template

from lobbies.twitch import get_twitch_spotlight


register = template.Library()


@register.inclusion_tag("partials/twitch_spotlight.html")
def twitch_spotlight(limit=6):
    return {
        "twitch_spotlight": get_twitch_spotlight(limit=limit),
    }
