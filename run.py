from app import create_app

app = create_app('development')

if __name__ == '__main__':
    print("\n Publicador Zap corriendo en http://localhost:5000\n")
    app.run(debug=True, port=5000, use_reloader=False)
