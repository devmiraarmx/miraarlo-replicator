import os
from app import create_app

# En producción FLASK_ENV=production; en dev se queda como 'development'
app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    print("\n Publicador Zap corriendo en http://localhost:5000\n")
    app.run(debug=True, port=5000, use_reloader=False)
