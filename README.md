# Python Tradervue API
This repository contains a Python implementation of the Tradervue API and small command line client example. The API currently supports all publicly available Tradervue endpoints:

   * Trade management
   * Importing & querying trade executions
   * User management
   * Journal entry management
   * Journal notes management

## Documentation

   * [Python Tradervue API](http://nall.github.io/py-tradervue-api/py-tradervue-api.html) (this library)
   * [Tradervue REST API](https://github.com/tradervue/api-docs)

## Example usage

```python
import datetime
from tradervue import Tradervue
tv = Tradervue(username, password, user_agent)
trades = tv.get_trades(symbol = 'OEX', startdate = datetime.date(2015, 9, 1))
for t in trades:
  print "Trade %s Profit/Loss: $%s" % (t['id'], t['gross_pl'])
```

## API TODO
   * Convert times to datetime objects
   * Make returned dicts objects with attributes instead
