import hashlib

def get_img_hash(img_bytes):
    return hashlib.md5(img_bytes).hexdigest()

def simplify_accessibility_tree(node):
    if not node:
        return None
    
    simplified = {
        "role": node.get("role"),
        "name": node.get("name"),
    }
    if node.get("description"):
        simplified["description"] = node.get("description")

    if "children" in node:
        children = [simplify_accessibility_tree(c) for c in node["children"]]
        children = [c for c in children if c and (c.get("name") or c.get("children"))]
        if children:
            simplified["children"] = children

    return simplified