import os
import random
import string

RAW_NEWS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../data/raw_news")
)

CHARSET = string.ascii_uppercase + string.digits
ID_LENGTH = 9


def generate_unique_argos_id():
    """
    Generate a unique 9-character ID (capital letters and numbers) not present in RAW_NEWS_DIR.
    Returns the unique ID as a string.
    """
    existing_ids = set()
    for root, dirs, files in os.walk(RAW_NEWS_DIR):
        for fname in files:
            if fname.endswith(".json") and len(fname) >= ID_LENGTH:
                existing_ids.add(fname[:ID_LENGTH])

    while True:
        new_id = "".join(random.choices(CHARSET, k=ID_LENGTH))
        if new_id not in existing_ids:
            return new_id


def add_argos_id_to_article(article_dict):
    """
    Add a unique argos_id to the article dict (in-place) if not present.
    Returns the argos_id.
    """
    if "argos_id" not in article_dict:
        article_dict["argos_id"] = generate_unique_argos_id()
    return article_dict["argos_id"]
