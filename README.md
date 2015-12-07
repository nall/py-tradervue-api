# Python Tradervue API
This repository contains a Python implementation of the Tradervue API and small command line client. The client currently can only create new trades. More functionality will be added as needed/requested.

This API is documented [here](http://nall.github.io/py-tradervue/py-tradervue.html).

The Tradervue REST API is documented [here](https://github.com/tradervue/api-docs). 

## OFX Importer
The tv-importofx requires the latest [ofxparse](https://github.com/jseutter/ofxparse) module to be installed. Currently, additional features are available in my fork. If you don't need option support, you can use the official repo. Here's an overview of tv-importofx usage:

    usage: tv-importofx [-h] [--account ACCOUNT] [--username USERNAME]
                        [--days DAYS] [--tag TAGS] [--account_tag ACCOUNT_TAG]
                        [--allow_duplicates] [--overlay_commissions] [--debug]
                        [--debug_http]
                        {set_password,delete_password,import}
    
    Tradervue OFX Importer
    
    positional arguments:
      {set_password,delete_password,import}
                            The action to perform
    
    optional arguments:
      -h, --help            show this help message and exit
      --account ACCOUNT, -a ACCOUNT
                            Use the specified ofxclient account ID (the local_id
                            field from ofxclient.ini). Required for imports.
      --username USERNAME, -u USERNAME
                            Tradervue username if different from $USER
      --days DAYS           The number of days of OFX data to download (default: 1)
      --tag TAGS            Add the specified tag to the imported executions. May
                            be specified multiple times.
      --account_tag ACCOUNT_TAG
                            Use the specified tag as the account tag during import. 
                            This tag is automatically added to the trade as well
      --allow_duplicates    disable Tradervue's automatic duplicate-detection when
                            importing this data
      --overlay_commissions
                            No new trades will be created and existing trades will
                            be updated with commission and fee data
      --debug               Enable verbose debugging messages
      --debug_http          Enable verbose HTTP request/response debugging messages

### Official ofxparse Repo

    pip install git+https://github.com/jseutter/ofxparse

### Forked ofxparse Repo (adds option support)

    pip install git+https://github.com/nall/ofxparse

### ofxclient
You also need to have the [ofxclient](https://github.com/captin411/ofxclient) installed.

    pip install ofxclient

### Setting up OFX accounts
The [ofxclient](https://github.com/captin411/ofxclient) package already has a nice mechanism for adding OFX accounts and managing passwords, etc. Thus, the initial setup of tv-importofx requires you to run ofxclient and setup your accounts. This should be a one time step unless you change your password or want to add an additional account.

After setting up your OFX account, add credentials for your Tradervue account by invoking tv-importofx with the `set_password` action:

    tv-importofx set_password --username <username>

This will prompt you for the password for <username> which is stored in your OS's keyring via the Python [keyring](https://github.com/jaraco/keyring) module. You can modify this password by rerunning the command above. You can delete the key with the delete\_password action:

    tv-importofx delete_password --username <username>

Once you've setup your OFX account(s) and Tradervue credentials, you're ready to start importing executions.

### Importing executions via OFX files
To import executions, you'll need the following:

   * Tradervue username (with valid credentials in the keyring as setup above)
   * ofxclient local\_id field for the account you're importing from. This can be found in `$HOME/ofxclient.ini`.
   * Number of days of transactions to import

Once you have the above, you can import with the following command (--days defaults to 1):

    tv-importofx import --username <tradervue_username> --account <ofxclient_account_id> [--days <num_days_to_import>]

#### Additional Import Options
There are a few (rarely used?) options available in the Tradervue import API that are exposed via the command line. To enable these options, specify the appropriate command line argument as described below. For more information on these options, see the Tradervue [import API](https://github.com/tradervue/api-docs/blob/master/imports.md).

   * `--allow_duplicates`: Specify this to disable Tradervue's automatic duplicate-detection when importing 
   * `--overlay_commissions`: If this is specified, nonew trades will be created, and existing trades will be updated with commission and fee data.

## API TODO
   * Convert times to datetime objects
   * Make returned dicts objects with attributes instead
