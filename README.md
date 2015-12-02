# Python TraderVue API
This repository contains a Python implementation of the TraderVue API and small command line client. The client currently can only create new trades. More functionality will be added as needed/requested.

## API
A brief overview of the Python API follows:

### Example Usage
```python
import tradervue
tv = tradervue.TraderVue(username, password, user_agent)
trades = tv.get_trades(symbol = 'OEX', startdate = datetime.date(2015, 9, 1))
for t in trades:
    print "Trade %s Profit/Loss: $%s" % (t['id'], t['gross_pl'])
```

---

#### TraderVue.__init__(username, password, user_agent, target_user = None)
Pretty self-explanatory. Create one of these to invoke the other API calls. Setting target_user will cause the Tradervue-UserId header to be set to that value on API calls.

#### TraderVue.create_trade(self, symbol, notes = None, initial_risk = None, shared = False, tags = [], return_url = False)
Create a new trade with no associated executions. Identical to the 'New Trade' functionality on the website.

Returns the trade ID if return_url is False, or the URL returned in the Location header if return_url is True. Returns None on error.

### TraderVue.delete_trade(self, trade_id)
Delete the specified trade. **CAUTION** -- this isn't reversible. Specify a single trade ID as the argument.

Returns True on successful deletion, False otherwise.

#### TraderVue.delete_trades(self, *trade_ids)
Delete the specified trades. **CAUTION** -- this isn't reversible. Specify 1 or more trade IDs as the arguments.

Returns a list of True/False values similar to delete_trade corresponding to the specified trade IDs.

#### TraderVue.get_trades(self, symbol = None, tag_expr = None, side = None, duration = None, startdate = None, enddate = None, max_trades = 25)
Query the database for trades matching the specified critiera. These are basically the same criteria as supported on the website. Note that side should be one of `long` or `short` and duration should be one of `intraday` or `multiday`. Also startdate and enddate should be datetime objects.

Returns a list of trades (a dict per trade) on success (list might have 0 length if no trades were found). Returns None on error.

#### TraderVue.get_trade(self, trade_id)
Get detailed information about the specified trade ID.

Returns a hash of trade info on success or None if an error occurs.

#### TraderVue.get_trade_executions(self, trade_id)
Get the execution info for the specified trade ID.

Returns a list of execution info on success or None if an error occurs.

#### TraderVue.get_trade_comments(self, trade_id)
Get the comments for the specified trade ID.

Returns a list of comments info on success or None if an error occurs.

#### TraderVue.update_trade(self, trade_id, notes = None, shared = None, initial_risk = None, tags = None)
Update the specified trade ID with new information. Only specify arguments you want to update. Others will be left unchanged.

Returns False on failure, True on success.

#### TraderVue.import_status(self)
Returns the current import status hash. This will have keys `status` and `info`. Returns None on error.

#### TraderVue.import_executions(self, executions, account_tag = None, tags = None, allow_duplicates = False, overlay_commissions = False, import_retries = 3, wait_for_completion = False, wait_retries = 3, secs_per_wait_retry = 15)
Imports the specified executions. The executions should be a list of hashes where each hash defines an execution. account_tag, tags, allow_duplicates, and overlay_commissions are documented in the [TraderVue API](https://github.com/tradervue/api-docs). For cases where there's already an import in progress, the import will be reattempted up to a maximum of `import_retries` times. If `wait_for_completion` is True, this function will block until the import has completed. While polling for completion, `wait_retries` and `secs_per_wait_retry` define how long to wait for results. If no results are available after that time, None is returned. On any error, None is returned. If `wait_for_completion` is True and results are found within the specified time, they are returned as succeeded/failure hash as defined in the TraderVue API.


