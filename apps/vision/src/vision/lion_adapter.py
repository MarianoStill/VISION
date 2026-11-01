import lion


def is_delivered(status):
    return lion.is_delivered(status)


def process_workbook(content, reference_date):
    return lion.process_workbook(content, reference_date)


def search_machines(model, query, mode="Todo", exact=False):
    return lion.search_machines(model, query, mode, exact)


def filter_machines(model, details, global_query="", filters=None, exact=False):
    return lion.filter_machines(model, details, global_query, filters, exact)


def stage_progress(status):
    return lion.stage_progress(status)
