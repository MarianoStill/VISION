from proof import project_inventory


def consume_inventory_projection(instances, dates, rules, grain, start, end):
    return project_inventory(instances, dates, rules, grain, start, end)
