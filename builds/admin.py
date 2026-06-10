from django.contrib import admin

from .models import BuildOrder, BuildOrderStep, MajorGod, Pantheon


class MajorGodInline(admin.TabularInline):
    model = MajorGod
    extra = 0


class BuildOrderStepInline(admin.TabularInline):
    model = BuildOrderStep
    extra = 1
    fields = (
        "order",
        "type",
        "label",
        "time",
        "food",
        "wood",
        "gold",
        "favor",
        "pop",
        "action",
        "note",
        "split_food",
        "split_wood",
        "split_gold",
        "split_favor",
        "split_pop",
    )


@admin.register(Pantheon)
class PantheonAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MajorGodInline]


@admin.register(MajorGod)
class MajorGodAdmin(admin.ModelAdmin):
    list_display = ("name", "pantheon", "focus")
    list_filter = ("pantheon",)
    search_fields = ("name", "slug", "title", "focus")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(BuildOrder)
class BuildOrderAdmin(admin.ModelAdmin):
    list_display = ("title", "major_god", "meta", "is_published", "updated_at")
    list_filter = ("is_published", "major_god__pantheon", "major_god")
    search_fields = ("title", "summary", "major_god__name")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [BuildOrderStepInline]


@admin.register(BuildOrderStep)
class BuildOrderStepAdmin(admin.ModelAdmin):
    list_display = ("build_order", "order", "time", "pop", "action")
    list_filter = ("build_order__major_god",)
    search_fields = ("action", "note", "label")