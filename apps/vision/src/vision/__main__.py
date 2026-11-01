from .integration import integrated_availability


def main() -> None:
    for module, status in integrated_availability().items():
        print(f"{module}: {status}")


if __name__ == "__main__":
    main()
