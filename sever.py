from http.server import SimpleHTTPRequestHandler, HTTPServer

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

server = HTTPServer(('127.0.0.1', 8000), CORSRequestHandler)
print("Serving on http://127.0.0.1:8000")
server.serve_forever()
