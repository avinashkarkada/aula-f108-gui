import sys

# no arguments opens the app, anything else goes to the command line tool
if len(sys.argv) > 1:
    from .cli import main
else:
    from .gui import main

sys.exit(main())
