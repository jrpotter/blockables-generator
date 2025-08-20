def load_env_file(filename=".env"):
    env = {}
    with open(filename, "r") as f:
        for line in f:
            eq_index = line.find("=")
            if eq_index == -1:
                continue
            key = line[:eq_index].strip()
            if all(map(lambda c: c.isalnum() or c == "_", key)):
                env[key] = line[eq_index + 1 :].strip()

    return env
