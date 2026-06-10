from django.db import models


class Pantheon(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    icon = models.CharField(max_length=255, blank=True)
    background = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MajorGod(models.Model):
    pantheon = models.ForeignKey(
        Pantheon,
        on_delete=models.CASCADE,
        related_name="major_gods",
    )

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    subtitle = models.CharField(max_length=160, blank=True)
    title = models.CharField(max_length=160, blank=True)
    focus = models.CharField(max_length=160, blank=True)
    bonuses = models.JSONField(default=list, blank=True)

    portrait = models.CharField(max_length=255, blank=True)
    breakout_portrait = models.CharField(max_length=255, blank=True)
    hud_ring = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["pantheon__name", "name"]

    def __str__(self):
        return self.name


class BuildOrder(models.Model):
    major_god = models.ForeignKey(
        MajorGod,
        on_delete=models.CASCADE,
        related_name="build_orders",
    )

    title = models.CharField(max_length=180)
    slug = models.SlugField()
    subtitle = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)
    meta = models.CharField(max_length=120, blank=True)

    goal_label = models.CharField(max_length=80, blank=True)
    goal_text = models.CharField(max_length=255, blank=True)
    goal_icon = models.CharField(max_length=255, blank=True)

    portrait = models.CharField(max_length=255, blank=True)

    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["major_god__name", "title"]
        unique_together = ("major_god", "slug")

    def __str__(self):
        return self.title


class BuildOrderStep(models.Model):
    build_order = models.ForeignKey(
        BuildOrder,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    order = models.PositiveIntegerField()

    type = models.CharField(max_length=40, blank=True)
    label = models.CharField(max_length=120, blank=True)

    time = models.CharField(max_length=24, blank=True)
    food = models.CharField(max_length=80, blank=True)
    wood = models.CharField(max_length=80, blank=True)
    gold = models.CharField(max_length=80, blank=True)
    favor = models.CharField(max_length=80, blank=True)
    pop = models.CharField(max_length=80, blank=True)

    action = models.TextField(blank=True)
    note = models.TextField(blank=True)

    split_food = models.PositiveIntegerField(default=0)
    split_wood = models.PositiveIntegerField(default=0)
    split_gold = models.PositiveIntegerField(default=0)
    split_favor = models.PositiveIntegerField(default=0)
    split_pop = models.CharField(max_length=24, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.build_order.title} — Row {self.order}"