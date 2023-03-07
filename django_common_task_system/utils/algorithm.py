

def list_to_tree(source, parent, cache=None):
    cache = cache or []
    tree = []
    for item in source:
        if item["id"] in cache:
            continue
        if item["parent"] == parent:
            cache.append(item["id"])
            item["children"] = list_to_tree(source, item["id"], cache)
            tree.append(item)
    return tree


def tree_to_list(tree, result=None):
    result = result or []
    for item in tree:
        result.append(item)
        if item.get("children", None):
            tree_to_list(item["children"], result)
    return result


def get_tree_by_id(tree, target_id):
    for item in tree:
        if item["id"] == target_id:
            return item
        if item.get("children", None):
            result = get_tree_by_id(item["children"], target_id)
            if result:
                return result
    return None
