import time
from flask import Flask, render_template, request
from search.engine import SearchEngine

# initialize flask app
app: Flask = Flask(__name__)

# initialize the engine once at startup to load the binary offsets into memory
engine: SearchEngine = SearchEngine("data/index")


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    """
    Main route for the search interface.
    Handles both rendering the search bar and processing queries.
    """
    query: str = ""
    results: list[tuple[str, float]] = []
    elapsed_ms: float = 0.0

    if request.method == "POST":
        # safely extract the query string from the form
        query = request.form.get("q", "").strip()
        
        if query:
            # track performance of the binary lookup
            t0: float = time.perf_counter()
            results = engine.search(query, top_k=10)
            elapsed_ms = (time.perf_counter() - t0) * 1000

    return render_template(
        "index.html", 
        query=query, 
        results=results, 
        time=elapsed_ms
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
