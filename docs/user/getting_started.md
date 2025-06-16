Getting Started
===============

You can always use the web interface to interact with HIPPO. In some scenarios,
however, you may want to interact with products and collections through a
command line or Pythonic interface. To do that, you'll need to make sure that
you have API keys set up and the correct packages installed. HIPPO uses SOAuth,
the centralized authentication solution for Simons Observatory services, to
ensure consistent access across various services to similar products.

Permissions System
------------------

The permission system for HIPPO is centered around SOAuth. You'll need to log
into the centralized management interface for SOAuth if you want to check your
permission level. To upload products to HIPPO, you'll have to have a
`hippo:write` grant that is provided to you by the administrators of your SOAuth
instance.

Groups
------

Write access to products and collections is handled on a per-group basis. Each
user has their own group, the same value as their username, but may be members
of other groups. 

This means that you'll need to ensure that you're a member of the correct groups
if you wish to receive access to protected resources. Some groups are special,
like `simonsobs`, which is given to users based upon their membership in their
`simonsobs` GitHub organization. Others are created by administrators and users
themselves. To be added or removed from a group, you'll need to ask the
administrator of the SOAuth instance.

Getting an API Key
------------------

API keys, likewise, are handled through SOAuth. You'll need to log in to the
SOAuth management interface, click Keys, and generate a new API key for HIPPO.

As soon as you've done this, you'll be able to see your API key once and only
once. You should copy it to your clipboard, and ensure that you have access to
the [soauth](https://pypi.org/project/soauth) package installed on your system,
and use:
```bash
soauth register hippo $YOUR_API_KEY
```
Note that API keys are machine dependent, so you can only use an API key on one
machine at any one time. If you want to access HIPPO from multiple machines,
you're free to create another API key.

### About API Key expiry

API keys for HIPPO, like all SOAuth services, are valid for six months. The
specific text contained within your API key will be invalidated after first use.
This is why we suggest that you always use the SOAuth provided tools to manage
your API key.

The API key is actually a refresh token, which is exchanged for an access token
or another refresh token on first invocation. This back-and-forth with the
SOAuth authentication service happens once every eight hours and is used to
prevent any stolen credential-style attacks.

### Refreshing your API Key

It can be easily refreshed using the SOAuth interface. When you refresh your
API key through this interface, you get another six months of expiry time before
it runs out. You can register it again using the same `soauth register hippo`
command described above.


Setting up Henry
----------------

Henry has two components, a command-line interface, and a Python interface.
They're both helpful ways that allow you to interact with HIPPO collections and
products.

To set up Henry, you'll need to create a little file in your home directory
called `.hippo.conf`. This is a JSON file with the following structure:

```json
{
  "host": "https://hippo.simonsobservatory.org",
  "verbose": true,
  "caches": [
    {"path": "/Users/myusername/hippo"}
  ],
  "default_readers": ["simonsobs"],
  "default_writers": []
}
```

There are five major components of this file. The first is the host on which the
HIPPO server is running. Generally, this will simply be
`https://hippo.simonsobservatory.org`.

Second is whether or not you want your Henry output
to be verbose. If this is set to true, then you'll get much more information
printed when using Henry and other HIPPO functionality.

Third is caches, which has its own section below.

Finally, there's the default readers and writers for products and collections
that you create. If these are left as an empty list or omitted, all products and
collections you create will only be visible by you and only be writable to by
you. If, for instance, you would like anybody who's part of the collaboration to
be able to read all the products you create, you should have `simonsobs` as a
member of your default readers. The groups which can read and write to your products
can always be modified later on if necessary.


Caches
------

When you 'realize' or download a product from HIPPO, the information will
actually be stored on disk in a cache. You can define as many caches as you
would like, and some centers have shared read-only caches of HIPPO products for
you to use. This reduces any unncessary duplication. If, however, you're trying
to use HIPPO on your own laptop or another machine, it's wise to set up a cache
in a consistent place. Consider a directory in your home folder called `hippo`
or `hippo_cache`. It can even be hidden (using the `.` prefix). The cache can
be managed through the use of the `henry` command line tool.