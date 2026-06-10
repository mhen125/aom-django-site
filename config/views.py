from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from builds.models import BuildOrder, MajorGod


def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap_xml"))
    body = f"""User-agent: *
Allow: /

Sitemap: {sitemap_url}
"""
    return HttpResponse(body, content_type="text/plain")


def sitemap_xml(request):
    urls = []

    def add(path, lastmod=None, changefreq="weekly", priority="0.6"):
        urls.append(
            {
                "loc": request.build_absolute_uri(path),
                "lastmod": lastmod,
                "changefreq": changefreq,
                "priority": priority,
            }
        )

    today = timezone.now().date().isoformat()

    add("/", today, "hourly", "1.0")
    add("/lobbies/", today, "hourly", "0.9")
    add("/build_orders/", today, "daily", "0.9")
    add("/agora/", today, "hourly", "0.5")

    for god in MajorGod.objects.all().only("slug"):
        add(f"/gods/{god.slug}/", today, "weekly", "0.75")

    builds = (
        BuildOrder.objects
        .filter(is_published=True)
        .only("slug", "updated_at")
        .order_by("major_god__slug", "slug")
    )

    for build in builds:
        lastmod = build.updated_at.date().isoformat() if build.updated_at else today
        add(f"/builds/{build.slug}/", lastmod, "weekly", "0.7")

    xml_urls = []
    for item in urls:
        xml_urls.append(
            "\n".join(
                [
                    "  <url>",
                    f"    <loc>{escape(item['loc'])}</loc>",
                    f"    <lastmod>{escape(item['lastmod'])}</lastmod>",
                    f"    <changefreq>{escape(item['changefreq'])}</changefreq>",
                    f"    <priority>{escape(item['priority'])}</priority>",
                    "  </url>",
                ]
            )
        )

    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *xml_urls,
            "</urlset>",
        ]
    )

    return HttpResponse(body, content_type="application/xml")
