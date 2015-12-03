Python TraderVue API
**************************
This is a Python implementation of the `TraderVue <https://www.tradervue.com>`_ API.

Below is a small example usage:

.. code-block:: python

  import datetime
  import tradervue
  tv = tradervue.TraderVue(username, password, user_agent)
  trades = tv.get_trades(symbol = 'OEX', startdate = datetime.date(2015, 9, 1))
  for t in trades:
    print "Trade %s Profit/Loss: $%s" % (t['id'], t['gross_pl'])

.. autoclass:: tradervue.TraderVue
    :members: 

