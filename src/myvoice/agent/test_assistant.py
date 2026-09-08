from myvoice.agent.assistant import run_command


def main() -> None:
    while True:
        command = input("You: ").strip()

        if command.lower() in {"exit", "quit"}:
            break

        response = run_command(command)

        print(f"MyVoice: {response}")


if __name__ == "__main__":
    main()