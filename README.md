HIPPO
=====

<p align="center">
<img src="hipposerve/web/static/logo.svg" style="width:30%"/>
</p>

The HIerarchical Product Post Office
------------------------------------

![Docker Image Version](https://img.shields.io/docker/v/simonsobs/hippo)

Hippo is a piece of software aimed at making FAIR (Findable, Attributable, Interoperable,
and Reuseable) data access easier. Through the use of the very flexible MongoDB for
_true_ metadata storage and MinIO as a data storage backend, hippo provides metadata-driven
access to reusable products.

Use-Cases
---------

Hippo is under development for the Advanced Simons Observatory, an NSF-funded telescope project
that aims to study, among other things, the Cosmic Microwave Background. Throughout the project,
many pieces of data will be produced: things like images, arrays, small databases, etc. Storing
and sharing these within the collaboration, and to the public, is a huge challenge; it's easy
enough to put them all in a big folder somewhere, but without associated metadata you will never
be able to find what you're looking for.

Enter hippo! Hippo allows you to upload data products and access them both manually and
programatically through a metadata-driven interaction.

Examples
--------

There are a number of example cases in the `example` directory. To lauch the development
server, you should run

```
python3 examples/simpleserve.py
```

This will create a test account (`admin`) with API key `TEST_API_KEY` and password
`TEST_PASSWORD`. You can use the upload scripts in `examples/{name}` that upload
data from the [NASA LAMBDA instance](https://lambda.gsfc.nasa.gov/product/act/actpol_prod_table.html).

You may need to copy `config.json` to `~/.hippo.conf` to correctly load the environment
or export appropriate variables.

Products can then be viewed through the web interface (served at `/web` from the
server root), or through the use of the `henry` command-line tool.

Containerized Version
---------------------

There is a containerized version of the application available in the repository. You can
build the container with `docker build .`. By default, the server runs on port 44776
(HIPPO on a T9 keyboard).

To actually run HIPPO, you will need a running instance of MongoDB and an instance
of an S3-compaitible storage server. HIPPO was built to be ran with MinIO. MinIO will
actually provide file storage for your server, with MongoDB handling the metadata.

There are a number of important configuration variables:

- `MINIO_URL`: hostname of the MINIO server as seen by the server.
- `MINIO_ACCESS`: the MINIO access token (username).
- `MINIO_SECRET`: the MINIO access secret (password).
- `MINIO_PRESIGN_URL`: hostname of the MINIO server as seen by external clients.
- `MONGO_URI`: the full URI for the mongo instance including password.
- `TITLE`: the title of the HIPPO instance.
- `DESCRIPTION`: the description of the HIPPO instance.
- `ADD_CORS`: boolean, whether to allow unlimited CORS access. True by default (dev)
- `DEBUG`: boolean, whether to run in debug mode. True by default (dev)
- `CREATE_TEST_USER`: boolean, whether to create a test user on startup. False.
- `TEST_USER_PASSWORD`: password of said test user.
- `TEST_USER_API_KEY`: a custom API key for your test user.
- `WEB`: boolean, whether to serve the web UI.
- `WEB_JWT_SECRET`: 32 bytes of hexidecimal data, secret for JWTs.
- `WEB_ALLOW_GITHUB_LOGIN`: whether to allow GitHub Login (False).
- `WEB_GITHUB_CLIENT_ID`: client ID for GitHub integration.
- `WEB_GITHUB_CLIENT_SECRET`: client secret for GitHub integration.
- `WEB_GITHUB_REQUIRED_ORGANISATION_MEMBERSHIP`: the GitHub organisation that users must be a part of to be granted access.

Secrets can be loaded from `/run/secrets` automatically, so long as they have the same file name as their environment variable.

For GitHub integration, your callback URL needs to be $URL/web.


Deployment Guide
----------------

To deploy, you need to set up a MongoDB server and a Minio server. This will involve:

- Creating a MongoDB password, saved as a secret.
- Creating a MongoDB URI with this password, saved as a secret.
- Creating a Minio access token, saved as a secret.
- Creating a WEB_JWT_SECRET, saved as a secret.
- Creating the GitHub client ID and secret, saved as a secret.

Then, you can deploy your MongoDB and Minio servers. Do not forget to set up storage
for their backends to ensure persistence across restarts.

Note that we provide a docker compose file in the main repository as an example. This
should show you how the containers interact.

With the two backends set up, you can deploy the container. You can build it yourself,
or use the hosted version.