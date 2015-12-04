# vim: filetype=python shiftwidth=2 tabstop=2 expandtab

"""
.. module:: tradervue
   :platform: Unix, Windows
   :synopsis: Implements the Tradervue API

.. moduleauthor:: Jon Nall <jon.nall@gmail.com>

"""

import copy
import json
import logging
import math
import re
import requests
import sys
import time

from colorama import Fore, Back, Style

# Print logging messages with a nice severity and some color
#
class TradervueLogFormatter(logging.Formatter):
  def format(self, record):
    prefix = suffix = severity = ''
    if record.levelno >= logging.ERROR:
      prefix = Fore.RED
      suffix = Fore.RESET
      severity = 'E'
    elif record.levelno >= logging.WARNING:
      prefix = Fore.YELLOW
      suffix = Fore.RESET
      severity = 'W'
    elif record.levelno >= logging.INFO:
      severity = 'I'
    elif record.levelno >= logging.DEBUG:
      severity = 'D'
    else:
      severity = '?'

    return '%s-%s- %-15s %s%s' % (prefix, severity, self.formatTime(record, datefmt = None), record.msg, suffix)

class Tradervue:
  """Here's some class stuff more
  """

  def __init__(self, username, password, user_agent, target_user = None, baseurl = 'https://www.tradervue.com', verbose_http = False):
    """Construct a Tradervue instance.

       :param str username: the Tradervue username
       :param str password: the Tradervue password
       :param str user_agent: the user agent to use in requests. Should be something like: ``MyApp (your@email.com)``
       :param target_user: the user id to issues requests on behalf of. To be used by organization administrators (if the feature is enabled)
       :param str baseurl: the organization's URL if using a local server
       :param bool verbose_http: set to True for verbose dumping of HTTP requests and reponses (requires logging of DEBUG severity to be enabled)
       :type target_user: str or None
       :return: the Tradervue instance
       :rtype: Tradervue
    """
    self.username = username
    self.password = password
    self.user_agent = user_agent
    self.target_user = target_user
    self.baseurl = '/'.join([baseurl, 'api', 'v1'])
    self.log = logging.getLogger('tradervue')
    self.verbose_http = verbose_http

  # Simple wrappers for requests API
  def __get   (self, url, params) : return self.__make_request(requests.get,    url, params = params)
  def __put   (self, url, payload): return self.__make_request(requests.put,    url, payload)
  def __post  (self, url, payload): return self.__make_request(requests.post,   url, payload)
  def __delete(self, url, payload): return self.__make_request(requests.delete, url, payload)

  def __make_request(self, request_fn, url, payload = None, params = None):
    auth = (self.username, self.password)
    headers = { 'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': self.user_agent }

    if payload is not None:
      payload = json.dumps(payload, indent = 2)

    # Add Target User header if that's been requested
    #
    if self.target_user is not None:
      headers['Tradervue-UserId'] = self.target_user

    if self.verbose_http:
      self.log.debug("%sREQUEST:  url     %s" % (Fore.GREEN, url))
      self.log.debug("          headers %s" % (headers))
      self.log.debug("          user    %s" % (auth[0]))
      self.log.debug("          payload %s" % (payload))
      self.log.debug("          params  %s" % (params))

    result = request_fn(url, headers = headers, auth = auth, data = payload, params = params)

    if self.verbose_http:
      self.log.debug("RESPONSE: url     %s" % (result.url))
      self.log.debug("          code    %s" % (result.status_code))
      self.log.debug("          headers %s" % (result.headers))
      self.log.debug("          body    %s%s" % (result.text, Fore.RESET))
    return result

  def __handle_bad_http_response(self, r, msg, show_url = False):

    # See if we can parse out a JSON error repsonse. If not, no big deal
    status = "HTTP Status: %d" % (r.status_code)
    if show_url:
      status += ", URL: %s" % (r.url)

    server_error = 'UNKNOWN'
    try:
      jdata = json.loads(r.text)
      if 'error' in jdata:
        server_error = jdata['error']
      elif 'status' in jdata:
        server_error = jdata['status']
      else:
        self.log.error("Unexpected JSON received for bad HTTP reponse (no status or error field found)")
        server_error = r.text
    except ValueError as e:
      server_error = r.text
      
    self.log.error(msg)
    self.log.error(status)
    self.log.error("Server error: %s" % (server_error))

    if r.status_code == 403 and self.target_user:
      self.log.error("No permission to issue API calls on behalf of user %d")

  def create_trade(self, symbol, notes = None, initial_risk = None, shared = False, tags = [], return_url = False):
    """Create a new trade. This is the equivalent of the 'New Trade' feature on the website.

       :param str symbol: The symbol for the trade
       :param notes: Any notes for the trade. Can include `Markdown <https://daringfireball.net/projects/markdown/>`_ syntax.
       :param initial_risk: The initial risk for the trade
       :param bool shared: True if this trade should be shared with other Tradervue users
       :param list tags: A list of tags to be applied to this trade. Each tag should be a string.
       :param bool return_url: If set to ``True``, the return value will be the value of the ``Location`` header. If ``False`` the trade ID is returned.
       :type notes: str or None
       :type initial_risk: float or None
       :return: The new trade ID if ``return_url`` is False or the Location URL if it is ``True``. ``None`` is returned if an error occurs.
       :rtype: str or None
    """
    url = '/'.join([self.baseurl, 'trades'])

    data = { 'symbol': symbol, 'shared': shared }
    if notes is not None: data['notes'] = notes
    if initial_risk is not None: data['initial_risk'] = initial_risk
    if len(tags) > 0: data['tags'] = copy.deepcopy(tags)

    r = self.__post(url, data)
    if r.status_code == 201:
      self.log.debug("Successfully created new trade for %s: %s" % (symbol, r.text))
      if return_url: 
        return r.headers['Location']
      else:
        payload = json.loads(r.text)
        return payload['id']
    else:
      self.__handle_bad_http_response(r, "New trade creation for %s" % (symbol))
      return None

  def delete_trades(self, *trade_ids):
    """Delete the specified trade IDs.

       :param str trade_ids: The trade IDs to be deleted.
       :return: A list of bool values (one per trade ID argument). ``True`` indicates the trade was deleted successfully. ``False`` indicates an error occured while deleting the trade ID.
       :rtype: list of bool
    """
    results = []
    trade_id = str(trade_id)

    for trade_id in trade_ids:
      if not self.delete_trade(trade_id):
        self.log.error("Unable to delete trade ID %s" % (trade_id))
        results.append(False)
      else:
        results.append(True)

    return results

  def delete_trade(self, trade_id):
    """Delete the specified trade ID.

       :param str trade_id: The trade ID to be deleted.
       :return: ``True`` if the trade was deleted successfully, ``False`` otherwise.
       :rtype: bool
    """
    trade_id = str(trade_id)
    url = '/'.join([self.baseurl, 'trades', trade_id])

    r = self.__delete(url, None)
    if r.status_code == 200:
      self.log.debug("Successfully deleted trade %s: %s" % (trade_id, r.text))
      return True
    else:
      self.__handle_bad_http_response(r, "Deletion of tradeID %s" % (trade_id))
      return False

  def get_trades(self, symbol = None, tag_expr = None, side = None, duration = None, startdate = None, enddate = None, winners = None, max_trades = 25):
    """Query for trades matching the specified criteria.

       All arguments to this method are optional. If not specified, they are not part of the query. 

       The list returned from this method contains dict objects which have fields as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param symbol: Find trades on this symbol
       :param tag_expr: Find trades matching this tag expression. Read more about tag expressions in this `blog entry <http://blog.tradervue.com/2012/10/10/new-tag-combination-report/>`_.
       :param side: Find trades matching the specified side. Must be one of the following values: ``'Long'`` or ``'Short'``.
       :param duration: Find trades matching the specified duration. Must be one of the following values: ``'Intraday'`` or ``'Multiday'``.
       :param startdate: Find trades occuring on or after the specified time
       :param enddate: Find trades occuring on or before the specified time
       :param winners: Find trades where the P&L is positive (or negative for a ``False`` value).
       :param max_trades: Return at most the specified number of trades
       :type symbol: str or None
       :type tag_expr: str or None
       :type side: str or None
       :type duration: str or None
       :type startdate: datetime or None
       :type enddate: datetime or None
       :type winners: bool or None
       :type max_trades: int or None
       :return: a list of trades matching the specified critiera or ``None`` if an error is encountered
       :rtype: list or none
    """
    data = { }
    if symbol is not None: data['symbol'] = symbol

    tag_warning_on_no_results = False
    if tag_expr is not None:
      if re.search(r'\sand\s', tag_expr) or re.search(r'\sor\s', tag_expr):
        # Dubious expression -- used and/or, but not uppercase which is required
        # If we don't return results, warn the user
        tag_warning_on_no_results = True
      data['tag'] = tag_expr

    if side is not None:
      if not re.match(r'^(long|short)$', side, re.IGNORECASE):
        raise ValueError("The 'side' parameter to get_trades must be 'Long' or 'Short'. Saw '%s'" % (side))
      else:
        data['side'] = side[0].upper()

    if duration is not None:
      if not re.match(r'^(intraday|multiday)$', duration, re.IGNORECASE):
        raise ValueError("The 'duration' parameter to get_trades must be 'Intraday' or 'Multiday'. Saw '%s'" % (duration))
      else:
        data['duration'] = duration[0].upper()

    if startdate is not None: data['startdate'] = startdate.strftime('%m/%d/%Y')
    if enddate is not None: data['enddate'] = enddate.strftime('%m/%d/%Y')
    if winners is not None: data['plgross'] = 'W' if winners else 'L'

    total_pages = 1
    if max_trades > 100:
      total_pages = int(math.ceil(max_trades / 100.0))

    all_trades = []
    for page in range(1, total_pages + 1):
      trades_left = max_trades - len(all_trades)
      data['page'] = page
      data['count'] = 100 if trades_left >= 100 else trades_left
      trades = self.__get_trades(data)
      if trades is None:
        self.log.debug("Found error condition when querying %s" % (data))
        return None
      elif len(trades) == 0:
        self.log.debug("No trades were found when querying %s" % (data))
        break
      else:
        self.log.debug("%d trade(s) were found when querying %s" % (len(trades), data))
        all_trades.extend(trades)

    if tag_warning_on_no_results and len(all_trades) == 0:
      self.log.warning("No results found for dubious tag expression '%s'. Make sure AND and OR are uppercase" % (tag_expr))

    return all_trades

  def __get_trades(self, data):
    url = '/'.join([self.baseurl, 'trades'])
    r = self.__get(url, data)
    if r.status_code == 200:
      self.log.debug("Successfully queried url %s" % (r.url))
      result = json.loads(r.text)
      if 'trades' not in result:
        self.log.error("No 'trades' field in query result for URL: %s\n%s" % (r.url, r.text))
        return None
      return result['trades']
    else:
      self.__handle_bad_http_response(r, "Unable to query trades", show_url = True)
      return None

  def get_trade(self, trade_id):
    """Get detailed information about the specified trade ID.

       The dict returned from this method contains keys as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param str trade_id: The trade ID to query.
       :return: a dict containing information about the trade ID or ``None`` on error.
       :rtype: dict or None
    """
    trade_id = str(trade_id)
    url = '/'.join([self.baseurl, 'trades', trade_id])

    r = self.__get(url, None)
    if r.status_code == 200:
      self.log.debug("Successfully queried trade ID %s" % (trade_id))
      return json.loads(r.text)
    else:
      self.__handle_bad_http_response(r, "Unable to query trade ID %s" % (trade_id), show_url = True)
      return None

  def get_trade_executions(self, trade_id):
    """Get detailed information about the executions of the specified trade ID.

       The dict returned from this method contains keys as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param str trade_id: The trade ID to query.
       :return: a dict containing information about the executions for trade ID or ``None`` on error.
       :rtype: dict or None
    """
    trade_id = str(trade_id)
    url = '/'.join([self.baseurl, 'trades', trade_id, 'executions'])

    r = self.__get(url, None)
    if r.status_code == 200:
      executions = json.loads(r.text)
      if 'executions' not in executions:
        self.log.error("Unable to find 'executions' key in executions results: %s" % (r.text))
        return None
      executions = executions['executions']
      self.log.debug("Successfully queried trade ID %s executions (found %d executions)" % (trade_id, len(executions)))
      return executions
    else:
      self.__handle_bad_http_response(r, "Unable to query trade ID %s executions" % (trade_id), show_url = True)
      return None

  def get_trade_comments(self, trade_id):
    """Get detailed information about the comments of the specified trade ID.

       The dict returned from this method contains keys as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param str trade_id: The trade ID to query.
       :return: a dict containing information about the comments for trade ID or ``None`` on error.
       :rtype: dict or None
    """
    trade_id = str(trade_id)
    url = '/'.join([self.baseurl, 'trades', trade_id, 'comments'])

    r = self.__get(url, None)
    if r.status_code == 200:
      comments = json.loads(r.text)
      if 'comments' not in comments:
        self.log.error("Unable to find 'comments' key in comments results: %s" % (r.text))
        return None
      comments = comments['comments']
      self.log.debug("Successfully queried trade ID %s comments (found %d comments)" % (trade_id, len(comments)))
      return comments
    else:
      self.__handle_bad_http_response(r, "Unable to query trade ID %s comments" % (trade_id), show_url = True)
      return None

  def update_trade(self, trade_id, notes = None, shared = None, initial_risk = None, tags = None):
    """Update fields of the specified trade ID.

       All arguments (other than ``trade_id``) to this method are optional. If not specified, that particular field won't be modified.

       :param str trade_id: The trade ID to update.
       :param notes: Any notes for the trade. Can include `Markdown <https://daringfireball.net/projects/markdown/>`_ syntax.
       :param shared: True if this trade should be shared with other Tradervue users
       :param initial_risk: The initial risk for the trade
       :param list tags: A list of tags to be applied to this trade. Each tag should be a string.
       :type notes: str or None
       :type shared: bool or None
       :type initial_risk: float or None
       :type tags: list or None
       :return: ``True`` if the trade was updated successfully, ``False`` otherwise.
       :rtype: bool
    """
    trade_id = str(trade_id)
    url = '/'.join([self.baseurl, 'trades', trade_id])

    data = {}
    if notes is not None: data['notes'] = notes
    if shared is not None: data['shared'] = shared
    if initial_risk is not None: data['initial_risk'] = initial_risk
    if tags is not None : data['tags'] = copy.deepcopy(tags)

    if len(data) == 0:
      self.log.warning("No updates specified for trade ID %s. Not taking further action" % (trade_id))
      return False

    r = self.__put(url, data)
    if r.status_code == 200:
      self.log.debug("Successfully updated fields [%s] of trade ID %s: %s" % (' '.join(data.keys()), trade_id, r.text))
      return True
    else:
      self.__handle_bad_http_response(r, "Unable to update fields [%s] of trade ID" % (' '.join(data.keys()), trade_id))
      return False

  def import_status(self):
    """Query status of the current import.

       The dict returned from this method contains keys as defined in the `Tradervue Import Documentation <https://github.com/tradervue/api-docs/blob/master/imports.md>`_.

       :return: a dict of the current import state or ``None`` on error
       :rtype: dict or None
    """
    url = '/'.join([self.baseurl, 'imports'])

    r = self.__get(url, None)
    if r.status_code == 200:
      self.log.debug("Successfully queried import status: %s" % (r.text))
      data = json.loads(r.text)
      status = data['status']
      if not status in ['ready', 'queued', 'processing', 'succeeded', 'failed' ]:
        self.log.error("Unexpected status '%s' for import status. Check API and update library" % (status))
        return None
      return data
    else:
      self.__handle_bad_http_response(r, "Unable to query import status")
      return None 

  def import_executions(self, executions, account_tag = None, tags = None, allow_duplicates = False, overlay_commissions = False, import_retries = 3, wait_for_completion = False, wait_retries = 3, secs_per_wait_retry = 15):
    """Import the specified trade executions.

       :param list executions: The executions to import. This should be a list of dicts. Each dict should have keys as specified in the `Tradervue Import Documentation <https://github.com/tradervue/api-docs/blob/master/imports.md>`_.
       :param account_tag: An account tag to use when importing. If ``None``, no account tag is used.
       :param tags: A list of tags to be applied to this trade. The list values should be strings. IF ``None``, no tags are applied to the trade.
       :param bool allow_duplicates: set this to ``True`` if you wish to disable Tradervue's automatic duplicate-detection when importing this data.
       :param bool overlay_commissions: set this to ``True`` to run this import in commission-overlay mode; no new trades will be created, and existing trades will be updated with commission and fee data. See the Tradervue `help article <http://www.tradervue.com/help/older_commissions>`_ for more details.
       :param int import_retries: Tradervue allows only one import at a time. If this method is invoked while Tradervue is busy, the import will be retried up to this many times before returning ``None``.
       :param bool wait_for_completion: If ``True``, this method will block until the import has been processed by Tradervue. In this case, the import success/failure information will be the return value from this method. Details on that data structure are available in the `Tradervue Import Documentation <https://github.com/tradervue/api-docs/blob/master/imports.md>`_.
       :param int wait_retries: The number of times to poll the import status before giving up and returning ``None``.
       :param int secs_per_wait_retry: The poll interval in seconds to query import status.
       :type account_tag: str or None
       :type tags: list or None
       :return: If ``wait_for_completion`` is ``True`` returns the import status dict or ``None`` on error. Otherwise returns ``True`` on success or ``False`` if an error occurs.
       :rtype: dict or None
       :raises ValueError: if ``executions`` is empty
       :raises TypeError: if ``executions`` or ``tags`` are not list objects
    """
    if len(executions) == 0:
      raise ValueError("Found 0 executions to import in import_executions. Must specify at least 1")
    if not isinstance(executions, list):
      raise TypeError("The executions argument to import_executions must be a list, but found %s" % (type(executions)))
    if tags is not None:
      if not isinstance(tags, list):
        raise TypeError("The tags argument (if specified) to import_executions must be a list, but found %s" % (type(tags)))
    
    data = { 'executions': copy.deepcopy(executions), 'allow_duplicates': allow_duplicates, 'overlay_commissions': overlay_commissions }

    # TV doesn't automatically add the account_tag. It must be explicitly added to the tags list
    if account_tag is not None:
      data['account_tag'] = account_tag
      if tags is None: tags = []
      if account_tag not in tags: tags.append(account_tag)

    if tags is not None: data['tags'] = copy.deepcopy(tags)

    return self.__import_executions(data, import_retries, wait_for_completion, wait_retries, secs_per_wait_retry)

  def __import_executions(self, data, import_retries, wait_for_completion, wait_retries, secs_per_wait_retry):
    url = '/'.join([self.baseurl, 'imports'])

    import_posted = False
    retries_left = import_retries
    while retries_left > 0:
      retries_left -= 1
      r = self.__post(url, data)
      if r.status_code == 200:
        data = json.loads(r.text)
        status = data['status']
        if not status in ['queued']:
          self.log.error("Unexpected status '%s' from importing executions: %s" % (status, r.text))
          return False
        else:
          self.log.debug("Import request successful: %s" % (r.text))
          import_posted = True
          break
      elif r.status_code == 424:
        data = json.loads(r.text)
        self.log.warning("Waiting 5 seconds and retrying import: %s" % (data['error']))
        time.sleep(5)
      else:
        self.__handle_bad_http_response(r, "Unable to import executions")
        return False

    if not import_posted:
      self.log.error("Unable to import executions after %d attempts. Giving up." % (import_retries))
      return False 
    elif wait_for_completion:
      self.log.debug("Waiting for import to complete...")

      retries_left = wait_retries
      data = self.import_status()

      while data is not None and (data['status'] == 'queued' or data['status'] == 'processing') and retries_left >= 0:
        retries_left -= 1
        time.sleep(secs_per_wait_retry)
        data = self.import_status()

      if data['status'] == 'ready':
        self.log.error("Found importer in ready state, but never saw success/failure")
        return None
      elif data['status'] == 'succeeded':
        self.log.debug("Import was successful")
        return data
      elif data['status'] == 'failure':
        self.log.error("Import had some failures")
        return data
      elif data['status'] in ['queued', 'processing']:
        self.log.error("Import is still being processed after %d attmpts to query status. Giving up" % (wait_retries))
        return None
      else:
        self.log.error("Unsupported import status '%s'" % (data['status']))
        return None
    else:
      return True

  def get_users(self):
    """Get the list of users for the organization.

       .. note::

          This method is only available to organization managers.

       The dict objects in the list returned from this method contains keys as defined in the `Tradervue User Documentation <https://github.com/tradervue/api-docs/blob/master/users.md>`_.

       :return: a list of users in the organization or ``None`` on error
       :rtype: list or None
    """
    url = '/'.join([self.baseurl, 'users'])

    r = self.__get(url, None)
    if r.status_code == 200:
      users = json.loads(r.text)
      if 'users' not in users:
        self.log.error("Unable to find 'users' key in users results: %s" % (r.text))
        return None
      users = users['users']
      self.log.debug("Successfully queried users (found %d users)" % (len(users)))
      return users
    else:
      self.__handle_bad_http_response(r, "Unable to query users", show_url = True)
      return None

  def get_user(self, user_id):
    """Get detailed information about the specified user ID.

       .. note::

          This method is only available to organization managers.

       The dict returned from this method contains keys as defined in the `Tradervue User Documentation <https://github.com/tradervue/api-docs/blob/master/users.md>`_.

       :return: information on the specified user ID or ``None`` if an error occurs
       :rtype: list or None
    """
    user_id = str(user_id)
    url = '/'.join([self.baseurl, 'users'])

    r = self.__get(url, None)
    if r.status_code == 200:
      user = json.loads(r.text)
      self.log.debug("Successfully queried user ID %s" % (user_id))
      return user
    else:
      self.__handle_bad_http_response(r, "Unable to query user ID %s" % (user_id), show_url = True)
      return None

  def update_user(self, user_id, username = None, email = None, plan = None):
    """Update fields for the specified user ID.

       .. note::

          This method is only available to organization managers.

       All arguments (other than ``user_id``) to this method are optional. If not specified, that particular field won't be modified.

       :param str user_id: the user ID to update
       :param username: the username for the specified user ID
       :param email: the email for the specified user ID
       :param plan: the Tradervue plan level. Should be one of ``'Free'``, ``'Silver'``, or ``'Gold'``.
       :type username: str or None
       :type email: str or None
       :type plan: str or None
       :return: ``True`` if the user ID was successfully updated, ``False`` otherwise
       :rtype: bool
    """
    user_id = str(user_id)
    url = '/'.join([self.baseurl, 'users'])

    r = self.__put(url, data)
    if r.status_code == 200:
      self.log.debug("Successfully updated fields [%s] of user ID %s: %s" % (' '.join(data.keys()), user_id, r.text))
      return True
    else:
      self.__handle_bad_http_response(r, "Unable to update fields [%s] of user ID" % (' '.join(data.keys()), user_id))
      return False

  def create_user(self, username, email, plan, password, trial_end = None):
    """Create a new user.

       .. note::

          This method is only available to organization managers.

       :param str username: the username for the new user
       :param str email: the email for the new user
       :param str plan: the Tradervue plan level for the new user. Should be one of ``'Free'``, ``'Silver'``, or ``'Gold'``.
       :param str password: the password for the new user
       :param trial_end: If specified, set a date for when the new user's trial period ends
       :type trial_end: datetime or None
       :return: the newly created user ID if successful or ``None`` if an error occurs
       :rtype: str or None
    """
    url = '/'.join([self.baseurl, 'users'])

    data = { 'username': username, 'plan': plan, 'email': email, 'password': password }
    if trial_end is not None: data['trial_end'] = trial_end.strftime('%Y-%m-%d')

    r = self.__post(url, data)
    if r.status_code == 201:
      payload = json.loads(r.text)
      user_id = payload['id']
      self.log.debug("Successfully created new user ID %s for %s: %s" % (user_id, username, r.text))
      return user_id
    else:
      self.__handle_bad_http_response(r, "New trade creation for %s" % (symbol))
      return None

