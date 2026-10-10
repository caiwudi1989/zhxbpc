def batches(items,size):
    batch=[]
    for item in items:
        batch.append(item)
        if len(batch)==size:
            yield batch; batch=[]
    if batch: yield batch
print(list(batches(range(7),3)))
