import http.server, socketserver, os

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # If the file path doesn't have an extension, force HTML header
        if not os.path.splitext(self.path)[1] and self.path != '/':
            self.send_header('Content-Type', 'text/html')
        super().end_headers()
    
socketserver.TCPServer(('', 8000), CustomHandler).serve_forever()