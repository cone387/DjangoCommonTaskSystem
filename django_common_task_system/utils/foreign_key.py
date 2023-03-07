from django.db.models import Model
from . import algorithm


def get_related_object_ids(obj: Model):
    user_categories = obj.__class__.objects.filter(user=obj.user).values('id', 'parent', 'name')
    tree = algorithm.list_to_tree(user_categories, obj.id)
    node = algorithm.get_tree_by_id(tree, obj.id)
    ids = [obj.id]
    object_list = algorithm.tree_to_list(node if node else tree)
    ids.extend([x['id'] for x in object_list])
    return ids


def get_unrelated_object_ids(obj: Model):
    pass
