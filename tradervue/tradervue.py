# vim: filetype=python shiftwidth=2 tabstop=2 expandtab
#
# Copyright (c) 2015, Jon Nall
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of tradervue-utils nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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

try:
  from colorama import Fore
except ImportError:
  class Fore:
    RED =    ''
    GREEN =  ''
    YELLOW = ''
    RESET =  ''

def color_text(color, text):
  return '%s%s%s' % (color, text, Fore.RESET)

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
      self.log.debug(color_text(Fore.GREEN, "REQUEST:  url     %s" % (url)))
      self.log.debug(color_text(Fore.GREEN, "          headers %s" % (headers)))
      self.log.debug(color_text(Fore.GREEN, "          user    %s" % (auth[0])))
      self.log.debug(color_text(Fore.GREEN, "          payload %s" % (payload)))
      self.log.debug(color_text(Fore.GREEN, "          params  %s" % (params)))

    result = request_fn(url, headers = headers, auth = auth, data = payload, params = params)

    if self.verbose_http:
      self.log.debug(color_text(Fore.GREEN, "RESPONSE: url     %s" % (result.url)))
      self.log.debug(color_text(Fore.GREEN, "          code    %s" % (result.status_code)))
      self.log.debug(color_text(Fore.GREEN, "          headers %s" % (result.headers)))
      self.log.debug(color_text(Fore.GREEN, "          body    %s" % (result.text)))
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

  def __delete_object(self, key, object_id):
    object_id = str(object_id)
    url = '/'.join([self.baseurl, key, object_id])

    r = self.__delete(url, None)
    if r.status_code == 200:
      self.log.debug("%s-DELETE[%s]: %s" % (key.upper(), object_id, color_text(Fore.GREEN, 'SUCCESS')))
      return True
    else:
      self.__handle_bad_http_response(r, "%s-DELETE[%s]: %s" % (key.upper(), object_id, color_text(Fore.RED, 'FAILED')))
      return False

  def __create_object(self, key, user_identifier, data, return_url):
    url = '/'.join([self.baseurl, key])

    r = self.__post(url, data)
    if r.status_code == 201:
      self.log.debug("%s-CREATE[%s]: %s" % (key.upper(), user_identifier, color_text(Fore.GREEN, 'SUCCESS')))
      if return_url:
        return r.headers['Location']
      else:
        payload = json.loads(r.text)
        return payload['id']
    else:
      self.__handle_bad_http_response(r, "%s-CREATE[%s]: %s" % (key.upper(), user_identifier, color_text(Fore.RED, 'FAILED')))
      return None

  def __update_object(self, key, object_id, data):
    object_id = str(object_id)

    if len(data) == 0:
      self.log.warning("No updates specified for %s ID %s. Not taking further action" % (key, object_id))
      return False

    url = '/'.join([self.baseurl, key, object_id])
    r = self.__put(url, data)
    if r.status_code == 200:
      self.log.debug("%s-UPDATE[%s]: (%s) %s" % (key.upper(), object_id, ' '.join(data.keys()), color_text(Fore.GREEN, 'SUCCESS')))
      return True
    else:
      self.__handle_bad_http_response(r, "%s-UPDATE[%s]: (%s) %s" % (key.upper(), object_id, ' '.join(data.keys()), color_text(Fore.RED, 'FAILED')))
      return False

  def __get_objects(self, key, data, result_key = None, max_objects = 25):
    total_pages = 1
    if max_objects > 100:
      total_pages = int(math.ceil(max_objects / 100.0))

    objects = []
    for page in range(1, total_pages + 1):
      objects_left = max_objects - len(objects)
      data['page'] = page
      data['count'] = 100 if objects_left >= 100 else objects_left
      cur_objects = self.__get_object(key, None, None, result_key, data)
      if cur_objects is None:
        self.log.error("Found error condition when querying %s" % (data))
        return None
      elif len(cur_objects) == 0:
        self.log.debug("No trades were found when querying %s" % (data))
        break
      else:
        self.log.debug("%d object(s) were found when querying %s" % (len(cur_objects), data))
        objects.extend(cur_objects)

    return objects


  def __get_object(self, endpoint, fragments, object_id, result_key = None, data = None):

    if fragments is None: fragments = []

    url_array = [self.baseurl, endpoint]
    if object_id is not None: url_array.append(str(object_id))
    url_array.extend(fragments)

    url = '/'.join(url_array)
    f_debug_string = '' if len(fragments) == 0 else '[%s]' % ('/'.join(fragments))

    r = self.__get(url, data)
    if r.status_code == 200:
      self.log.debug("%s-GET[%s]%s: %s" % (endpoint.upper(), object_id, f_debug_string, color_text(Fore.GREEN, 'SUCCESS')))
      result = json.loads(r.text)
      if result_key is not None:
        if result_key not in result:
          self.log.error("Unable to find '%s' key in %s results: %s" % (result_key, endpoint, r.text))
          return None
        else:
          return result[result_key]
      else:
        return result
    else:
      self.__handle_bad_http_response(r, "%s-GET[%s]%s: %s" % (endpoint.upper(), object_id, f_debug_string, color_text(Fore.RED, 'FAILED')), show_url = True)
      return None

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
    data = { 'symbol': symbol, 'shared': shared }
    if notes is not None: data['notes'] = notes
    if initial_risk is not None: data['initial_risk'] = initial_risk
    if tags is not None and len(tags) > 0: data['tags'] = copy.deepcopy(tags)

    return self.__create_object('trades', symbol, data, return_url)

  def delete_trade(self, trade_id):
    """Delete the specified trade ID.

       :param str trade_id: The trade ID to be deleted.
       :return: ``True`` if the trade was deleted successfully, ``False`` otherwise.
       :rtype: bool
    """
    return self.__delete_object('trades', trade_id)

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
       :type startdate: date or datetime or None
       :type enddate: date or datetime or None
       :type winners: bool or None
       :type max_trades: int or None
       :return: a list of trades matching the specified critiera or ``None`` if an error is encountered
       :rtype: list or None
    """
    data = { }
    if symbol is not None: data['symbol'] = symbol

    tag_warning_on_no_results = False
    if tag_expr is not None:
      if re.search(r'\sand\s', tag_expr) or re.search(r'\sor\s', tag_expr):
        # Dubious expression -- used and/or, but not upper which is required
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

    all_trades = self.__get_objects('trades', data, 'trades', max_trades)

    if tag_warning_on_no_results and len(all_trades) == 0:
      self.log.warning("No results found for dubious tag expression '%s'. Make sure AND and OR are upper" % (tag_expr))

    return all_trades

  def get_trade(self, trade_id):
    """Get detailed information about the specified trade ID.

       The dict returned from this method contains keys as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param str trade_id: The trade ID to query.
       :return: a dict containing information about the trade ID or ``None`` on error.
       :rtype: dict or None
    """
    return self.__get_object('trades', None, trade_id)

  def get_trade_executions(self, trade_id):
    """Get detailed information about the executions of the specified trade ID.

       The dict returned from this method contains keys as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param str trade_id: The trade ID to query.
       :return: a dict containing information about the executions for trade ID or ``None`` on error.
       :rtype: dict or None
    """
    return self.__get_object('trades', ['executions'], trade_id, 'executions')

  def get_trade_comments(self, trade_id):
    """Get detailed information about the comments of the specified trade ID.

       The dict returned from this method contains keys as defined in the `Tradervue Trade Documentation <https://github.com/tradervue/api-docs/blob/master/trades.md>`_.

       :param str trade_id: The trade ID to query.
       :return: a dict containing information about the comments for trade ID or ``None`` on error.
       :rtype: dict or None
    """
    return self.__get_object('trades', ['comments'], trade_id, 'comments')

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
    data = {}
    if notes is not None: data['notes'] = notes
    if shared is not None: data['shared'] = shared
    if initial_risk is not None: data['initial_risk'] = initial_risk
    if tags is not None : data['tags'] = copy.deepcopy(tags)

    return self.__update_object('trades', trade_id, data)

  def import_status(self):
    """Query status of the current import.

       The dict returned from this method contains keys as defined in the `Tradervue Import Documentation <https://github.com/tradervue/api-docs/blob/master/imports.md>`_.

       :return: a dict of the current import state or ``None`` on error
       :rtype: dict or None
    """
    result = self.__get_object('imports', None, None)
    if not 'status' in result:
      self.log.error("Unable to find 'status' key in result: %s" % (result))
      return None 
    elif not result['status'] in ['ready', 'queued', 'processing', 'succeeded', 'failed' ]:
      self.log.error("Unexpected status '%s' for import status. Check API and update library. Result = %s" % (status, result))
      return None
    return result

  def import_executions(self, executions, account_tag = None, tags = None, allow_duplicates = False, overlay_commissions = False, import_retries = 3, wait_for_completion = False, wait_retries = 5, secs_per_wait_retry = 3):
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
      elif data['status'] == 'failed':
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
    return self.__get_object('users', None, None, 'users')

  def get_user(self, user_id):
    """Get detailed information about the specified user ID.

       .. note::

          This method is only available to organization managers.

       The dict returned from this method contains keys as defined in the `Tradervue User Documentation <https://github.com/tradervue/api-docs/blob/master/users.md>`_.

       :return: information on the specified user ID or ``None`` if an error occurs
       :rtype: list or None
    """
    return self.__get_object('users', None, user_id, 'users')

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
    data = {}
    if username is not None: data['username'] = username
    if email is not None: data['plan'] = email
    if plan is not None: data['plan'] = plan

    return self.__update_object('users', user_id, data)

  def create_user(self, username, email, plan, password, trial_end = None, return_url = False):
    """Create a new user.

       .. note::

          This method is only available to organization managers.

       :param str username: the username for the new user
       :param str email: the email for the new user
       :param str plan: the Tradervue plan level for the new user. Should be one of ``'Free'``, ``'Silver'``, or ``'Gold'``.
       :param str password: the password for the new user
       :param trial_end: If specified, set a date for when the new user's trial period ends
       :type trial_end: date or datetime or None
       :param bool return_url: If set to ``True``, the return value will be the value of the ``Location`` header. If ``False`` the trade ID is returned.
       :return: the new user ID if ``return_url`` is False or the Location URL if it is ``True``. ``None`` is returned if an error occurs.
       :rtype: str or None
    """
    data = { 'username': username, 'plan': plan, 'email': email, 'password': password }
    if trial_end is not None: data['trial_end'] = trial_end.strftime('%Y-%m-%d')

    return self.__create_object('users', username, data, return_url)

  def get_journals(self, date = None, startdate = None, enddate = None, max_journals = 25):
    """Query for journal entries matching the specified criteria.

       All arguments to this method are optional. If not specified, they are not part of the query. 

       The list returned from this method contains dict objects which have fields as defined in the `Tradervue Journal Documentation <https://github.com/tradervue/api-docs/blob/master/journal.md>`_.

       :param date: Find journal entry for the specified date. If this argument is used, neither ``startdate`` nor ``enddate`` should be specified.
       :param startdate: Find journal entries occuring on or after the specified time. Do not use if ``date`` is specified.
       :param enddate: Find journal entries occuring on or before the specified time. Do not use if ``date`` is specified.
       :param max_journals: Return at most the specified number of journal entries
       :type date: date or datetime or None
       :type startdate: date or datetime or None
       :type enddate: date or datetime or None
       :type max_journals: int or None
       :return: a list of journal entries matching the specified critiera or ``None`` if an error is encountered
       :rtype: list or None
    """
    if date is not None and (startdate is not None or enddate is not None):
      raise ValueError, "Cannot specify startdate or enddate if date is specified"

    data = { }
    if date is not None: data['d'] = date.strftime('%m/%d/%Y')
    if startdate is not None: data['startdate'] = startdate.strftime('%m/%d/%Y')
    if enddate is not None: data['enddate'] = enddate.strftime('%m/%d/%Y')

    return self.__get_objects('journal', data, 'journal_entries', max_journals)

  def get_journal(self, journal_id = None, date = None):
    """Get detailed information about the specified journal ID (or the journal on the specified date). Exactly one of ``journal_id`` or ``date`` must be specified.

       The dict returned from this method contains keys as defined in the `Tradervue Journal Documentation <https://github.com/tradervue/api-docs/blob/master/journal.md>`_.

       :param journal_id: The journal ID to query.
       :param date: The date to query
       :type journal_id: str or None
       :type date: or datetime or None
       :return: a dict containing information about the journal ID or ``None`` on error.
       :rtype: dict or None
    """
    if journal_id is not None and date is not None:
      raise ValueError("Must not specify both journal_id and date to get_journal")
    elif journal_id is None and date is None:
      raise ValueError("Must specify either journal_id or date to get_journal")

    if journal_id is not None:
      return self.__get_object('journal', None, journal_id)
    else:
      journals = self.get_journals(date = date, max_journals = 1)
      if journals is None or len(journals) == 0:
        return None
      else:
        return self.get_journal(journals[0]['id'])

  def update_journal(self, journal_id, notes = None):
    """Update fields of the specified journal ID.

       All arguments (other than ``journal_id``) to this method are optional. If not specified, that particular field won't be modified.

       :param str journal_id: The journal ID to update.
       :param notes: Any notes for the journal entry. Can include `Markdown <https://daringfireball.net/projects/markdown/>`_ syntax.
       :type notes: str or None
       :return: ``True`` if the journal was updated successfully, ``False`` otherwise.
       :rtype: bool
    """
    data = {}
    if notes is not None: data['notes'] = notes

    return self.__update_object('journal', journal_id, data)

  def create_journal(self, date, notes = None, return_url = False):
    """Create a new journal entry. This is the equivalent of the 'Create New Journal Entry' feature on the website.

       :param date: The date of the journal entry
       :param notes: Any notes for the journal entry. Can include `Markdown <https://daringfireball.net/projects/markdown/>`_ syntax.
       :param bool return_url: If set to ``True``, the return value will be the value of the ``Location`` header. If ``False`` the journal ID is returned.
       :type date: date or datetime or None
       :type notes: str or None
       :return: The new journal ID if ``return_url`` is False or the Location URL if it is ``True``. ``None`` is returned if an error occurs.
       :rtype: str or None
    """
    data = { 'date': date.strftime('%Y-%m-%d') }
    if notes is not None: data['notes'] = notes

    return self.__create_object('journal', data['date'], data, return_url)

  def delete_journal(self, journal_id):
    """Delete the specified journal ID.

       :param str journal_id: The journal ID to be deleted.
       :return: ``True`` if the journal entry was deleted successfully, ``False`` otherwise.
       :rtype: bool
    """
    return self.__delete_object('journal', journal_id)

  def get_notes(self, max_notes = 25):
    """Query for journal notes.

       The list returned from this method contains dict objects which have fields as defined in the `Tradervue Journal Notes Documentation <https://github.com/tradervue/api-docs/blob/master/notes.md>`_.

       :param max_notes: Return at most the specified number of journal notes
       :type max_notes: int or None
       :return: a list of journal notes or ``None`` if an error is encountered
       :rtype: list or None
    """
    return self.__get_objects('notes', {}, 'journal_notes', max_notes)

  def get_note(self, note_id):
    """Get detailed information about the specified journal note ID.

       The dict returned from this method contains keys as defined in the `Tradervue Journal Notes Documentation <https://github.com/tradervue/api-docs/blob/master/notes.md>`_.

       :return: information on the specified journal note ID or ``None`` if an error occurs
       :rtype: list or None
    """
    return self.__get_object('notes', None, note_id)

  def update_note(self, note_id, notes = None):
    """Update fields of the specified journal note ID.

       All arguments (other than ``note_id``) to this method are optional. If not specified, that particular field won't be modified.

       :param str note_id: The journal not ID to update.
       :param notes: Any notes for the journal note entry. Can include `Markdown <https://daringfireball.net/projects/markdown/>`_ syntax.
       :type notes: str or None
       :return: ``True`` if the journal note was updated successfully, ``False`` otherwise.
       :rtype: bool
    """
    data = {}
    if notes is not None: data['notes'] = notes

    return self.__update_object('notes', note_id, data)

  def create_note(self, notes = None, return_url = False):
    """Create a new journal note entry. This is the equivalent of the 'Create New Note' feature on the website.

       :param notes: Any notes for the journal entry. Can include `Markdown <https://daringfireball.net/projects/markdown/>`_ syntax.
       :param bool return_url: If set to ``True``, the return value will be the value of the ``Location`` header. If ``False`` the journal ID is returned.
       :type notes: str or None
       :return: The new journal note ID if ``return_url`` is False or the Location URL if it is ``True``. ``None`` is returned if an error occurs.
       :rtype: str or None
    """
    data = {}
    if notes is not None: data['notes'] = notes

    return self.__create_object('notes', '', data, return_url)

  def delete_note(self, note_id):
    """Delete the specified journal note ID.

       :param str note_id: The journal note ID to be deleted.
       :return: ``True`` if the journal note entry was deleted successfully, ``False`` otherwise.
       :rtype: bool
    """
    return self.__delete_object('notes', note_id)

