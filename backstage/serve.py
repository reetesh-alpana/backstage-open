import argparse
import sys

class SimpleServer(object):

    def __init__(self, host, port, **options):
        self.host = host
        self.port = port
        self.options = options

    def run(self, application):
        from wsgiref import simple_server
        httpd = simple_server.make_server(self.host, self.port, application)

        print "Starting backstage server using wsgi @ %s" % (self.port)
        print "Press Ctrl + C to exit"
        httpd.serve_forever()

class GunicornServer(object):

    def __init__(self, host, port, **options):
        self.host = host
        self.port = port
        self.options = options

    def run(self, application):
        from gunicorn.app.base import Application

        options = {'bind': "%s:%d" % (self.host, self.port)}
        options.update(self.options)

        class GunicornApplication(Application):
            def init(self, parser, opts, args):
                return options

            def load(self):
                return application

        print "Starting gunicorn server using wsgi @ %s" % (self.port)
        print "Press Ctrl + C to exit"

        GunicornApplication().run()

servers = {'simple': SimpleServer, 'gunicorn': GunicornServer}

def serve():
    parser = argparse.ArgumentParser(description='Run backstage server with various options')
    parser.add_argument('type', type=str, default='simple', help='Select a server type as defined in the server map')
    parser.add_argument('parse', type=str, help='Directory/File to be parsed')
    parser.add_argument('host', type=str, help='Host')
    parser.add_argument('port', type=int, help='Port')

    parser.add_argument('--options', default='', type=str,
                        help='Options in the format workers=1,option=value,option=value according to the server type')

    parser.add_argument('--settings', default='settings', type=str,
                        help='Settings file for the backstage server to use')

    options_dict = {}
    args = parser.parse_args()
    if args.options:
        options_dict = dict((p.split('=') for p in args.options.split(',')))
        """
        Pop the last two values out of sys.argv since gunicorn throws an exception after readin sys.argv, we are settings
        """
        for x in range(0, 4):
            sys.argv.pop()


    server = servers[args.type](args.host, args.port, **options_dict)
    
    sys.path.append(args.settings)    
    folder_path = args.settings.split(",")    
    # Import the settings module    
    sys.path.extend(folder_path)    
    __import__('settings') 

    from backstage.core import application, run
    from backstage.conf import settings

    # Parse the xml input files
    run()

    server.run(application)
