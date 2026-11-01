def is_delivered(status):
    return "Entregadas" in str(status).split(" | ")
