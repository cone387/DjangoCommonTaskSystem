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


def get_model_related(model, parent='', excludes=None, related=None):
    related = related or []
    for field in model._meta.fields:
        t = field.__class__.__name__
        if t == 'ForeignKey' and parent.split("__")[-1] != field.name:
            if excludes and field.related_model in excludes:
                continue
            if parent:
                child = parent + "__" + field.name
            else:
                child = field.name
            related.append(child)
            get_model_related(field.related_model, parent=child, excludes=excludes, related=related)
    return related
