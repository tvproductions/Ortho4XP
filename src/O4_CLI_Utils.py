def print_build_result(result) -> None:
    for message in build_result_messages(result):
        print(message)


def build_result_messages(result) -> tuple[str, ...]:
    if result.ok:
        return ("Bon vol!",)
    if result.message:
        return (result.message, "Crash!")
    return ("Crash!",)
