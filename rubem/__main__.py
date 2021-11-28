try:
    from cli import main
except ImportError:
    from .cli import main

if __name__ == "__main__":
    main()
