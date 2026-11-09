"""The nine technology categories (Application, Database, Identity...) and how they are grouped."""

from django.db import models


class Category(models.TextChoices):
    APPLICATION = "application", "Application"
    DATABASE = "database", "Database"
    OPERATING_SYSTEM = "operating_system", "Operating system"
    JOBS = "jobs", "Jobs and interfaces"
    NETWORK = "network", "Network"
    IDENTITY = "identity", "Identity"
    CLOUD = "cloud", "Cloud and containers"
    ENGINEERING_TOOLS = "engineering_tools", "Engineering tools"
    LOGGING = "logging", "Logging and monitoring"

    @property
    def heading(self):
        return HEADINGS[self]


# The heading above each category's guidance.
HEADINGS = {
    Category.APPLICATION: "A well-controlled application",
    Category.DATABASE: "A well-controlled database",
    Category.OPERATING_SYSTEM: "A well-controlled server",
    Category.JOBS: "Well-controlled jobs and interfaces",
    Category.NETWORK: "A well-controlled network",
    Category.IDENTITY: "A well-controlled identity service",
    Category.CLOUD: "A well-controlled cloud environment",
    Category.ENGINEERING_TOOLS: "Well-controlled engineering tools",
    Category.LOGGING: "Well-controlled logging",
}

CATEGORY_KEYS = frozenset(Category.values)

STACK = (
    Category.APPLICATION,
    Category.DATABASE,
    Category.OPERATING_SYSTEM,
    Category.JOBS,
    Category.NETWORK,
)
SHARED_SERVICES = (
    Category.IDENTITY,
    Category.CLOUD,
    Category.ENGINEERING_TOOLS,
    Category.LOGGING,
)
# Headings for the platforms index, in display order.
GROUPS = (("The stack", STACK), ("Shared services", SHARED_SERVICES))


def group_title(category):
    return GROUPS[0][0] if category in STACK else GROUPS[1][0]
