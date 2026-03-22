from flask import Flask, jsonify, render_template
from flask_cors import CORS
import time
import threading
import logging
from scanner import run_scan, SYMBOL_PAIR, TIMEFRAMES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
CORS(app)

# Simple in-memory cache
_cache = {
    'data': [],
    'last_updated': None,
    'is_loading': False,
}
CACHE_TTL = 60  # seconds


def refresh_cache():
    if _cache['is_loading']:
        return
    _cache['is_loading'] = True
    try:
        logger.info("Fetching scan data...")
        data = run_scan(SYMBOL_PAIR)
        _cache['data'] = data
        _cache['last_updated'] = time.time()
        logger.info(f"Cache refreshed: {len(data)} results")
    except Exception as e:
        logger.error(f"Cache refresh error: {e}")
    finally:
        _cache['is_loading'] = False


def background_refresh():
    while True:
        refresh_cache()
        time.sleep(CACHE_TTL)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/scan')
def api_scan():
    now = time.time()
    if not _cache['data'] or (now - (_cache['last_updated'] or 0)) > CACHE_TTL:
        refresh_cache()

    return jsonify({
        'symbol': SYMBOL_PAIR,
        'timeframes': TIMEFRAMES,
        'results': _cache['data'],
        'last_updated': _cache['last_updated'],
        'is_loading': _cache['is_loading'],
    })


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    # Initial load in background
    t = threading.Thread(target=background_refresh, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=5000, debug=False)
