"""Main module."""

import asyncio
import sys
from .application import create_app
from time import time



if '--test' in sys.argv:
    async def test_async(app, n):
        client = app.asgi_client
        st = time()
        for _ in range(n):
            req, res = await client.get('/a')
            # req, res = await client.get('/s')
        et = time()
        print(f'async x {n:,}: took: {et-st:.4f} secs, {n*(1/(et-st)):.4} req/sec')

    n = 750
    print(*sys.argv[1:])
    asyncio.run(test_async(create_app('--di' in sys.argv), n))

else:
    app = create_app('--di' in sys.argv)
    app.run(host="0.0.0.0", port=8000, debug='-d' in sys.argv)


