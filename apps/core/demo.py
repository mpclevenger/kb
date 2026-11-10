"""Demo content for TRAC: an FAQ (real guides, controls, drivers and guidance come from content/).

Used only by `manage.py load_demo`. Everything here is created as a draft; the command
then publishes it. Each function skips itself when its content already exists.
"""

from apps.core import versioning as v
from apps.topics.models import Stage, Topic
from apps.wiki.models import Faq, FaqVersion

DEMO_FAQ_QUESTION = "Do service accounts need to be in the periodic access review?"


def stage(topic, name):
    return Stage.objects.get(topic=topic, name=name)


def add_faq(author):
    if FaqVersion.objects.filter(question=DEMO_FAQ_QUESTION).exists():
        return False
    v.create_entity(
        Faq, FaqVersion, author,
        question=DEMO_FAQ_QUESTION,
        answer="Yes. Service accounts can change data like any user, so include them and confirm each one "
               "still has an owner.",
        topic=Topic.objects.get(id_prefix="MA"),
    )
    return True
