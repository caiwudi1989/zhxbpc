strategies={"upper":str.upper,"lower":str.lower}
def process(text,mode):
    if mode not in strategies: raise ValueError("unsupported")
    return strategies[mode](text)
print(process("Hello","upper"),process("Hello","lower"))
