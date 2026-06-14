def add(x, acc=None):
    if acc is None:
        acc = []
    acc.append(x)
    return list(acc)
