Command-Line Interface
======================

Before getting started, make sure you've followed the instructions in the
[getting started](getting_started.md) guide to get an API key.  The command-line
interface for HIPPO is known as `henry`, and contains a large suite of commands,
primarily for manging your local cache, searching for products, and managing
product and collection relationships (TBD).

Commands with henry are structured as follows:
```bash
henry $VALUE $COMMAND ...
```
Where `$VALUE` is the type of data or object that you want to manage. To view
all top-level commands, you can type
```bash
henry --help
>>> product      Commands for dealing directly with products
>>> collection   Commands for dealing with collections 
>>> cache        Maintenance commands for the cache. There are also tools for cache management in the product and collection commands.
>>> dev          Developer commands, mainly used for running and testing servers during hippo development. For regular use, you can ignore these.
```
You can then view the individual commands for the object type, for example
```bash
henry product --help
>>> read            Read the information of a product by its ID. You can find the relationship between product names and IDs through the product search command.
>>> delete          Delete a product by its ID.
>>> search          Search for products by name.
>>> cache           Cache a product by its ID.
>>> uncache         Uncache a product by its ID.
>>> edit            Edit a product by its ID.
>>> add-reader      Add a reader (by group name) to a product.
>>> remove-reader   Remove a reader (by group name) from a product
>>> add-writer      Add a writer (by group name) to a product
>>> remove-writer   Remove a writer (by group name) from a product
```
Help on the parameters available for an individual command is availble - you guessed it -
through the use of `--help`:
```bash 
henry product read --help
```
which prints information on the parameters and types of those parameters.


Reading Products and Collections
--------------------------------

If you know the ID of the collection or product you'd like to read, you can always just use
the `read` command, e.g.

```bash
henry collection read 6851be3dc869d741c82d6964 
```
```
Successfully read collection ACT DR4 Frequency Maps at 98 and 150 GHz presented in Aiola et al. 2020 (6851be3dc869d741c82d6964)
ACT DR4 Frequency Maps at 98 and 150 GHz presented in Aiola et al. 2020

These FITS files are the maps made with the nighttime 2013(s13) to 2016(s16) data from the ACTPol camera on the ACT telescope at 98(f090) and    
150(f150) GHz...                                      

                                          Products                                          
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃            ID            ┃ Name                             ┃ Version ┃     Uploaded     ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ 6851be3dc869d741c82d6965 │ ACT DR4 (Patch D5) 4-way (set2)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be3fc869d741c82d696a │ ACT DR4 (Patch D6) 4-way (coadd) │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be41c869d741c82d696f │ ACT DR4 (Patch D6) 4-way (set0)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be43c869d741c82d6974 │ ACT DR4 (Patch D1) 4-way (set2)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be44c869d741c82d6979 │ ACT DR4 (Patch D1) 4-way (set1)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be45c869d741c82d697e │ ACT DR4 (Patch D5) 4-way (set0)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be47c869d741c82d6983 │ ACT DR4 (Patch D6) 4-way (set3)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be49c869d741c82d6988 │ ACT DR4 (Patch D5) 4-way (set1)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be4bc869d741c82d698d │ ACT DR4 (Patch D1) 4-way (set0)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be4dc869d741c82d6992 │ ACT DR4 (Patch D5) 4-way (coadd) │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be4fc869d741c82d6997 │ ACT DR4 (Patch D6) 4-way (set1)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be51c869d741c82d699c │ ACT DR4 (Patch D5) 4-way (set3)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be53c869d741c82d69a1 │ ACT DR4 (Patch D6) 4-way (set2)  │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be55c869d741c82d69a6 │ ACT DR4 (Patch D1) 4-way (coadd) │  1.0.0  │ 2025-06-17 19:13 │
│ 6851be56c869d741c82d69ab │ ACT DR4 (Patch D1) 4-way (set3)  │  1.0.0  │ 2025-06-17 19:13 │
└──────────────────────────┴──────────────────────────────────┴─────────┴──────────────────┘
```
You can always find the ID of products and collections on their names in the web UI. `henry`
also provides search functionality:
```bash
henry collection search act
```
```
Successfully searched for collection act
                                                 Collections                                                  
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃            ID            ┃ Name                                   ┃ Description                            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 6851be3dc869d741c82d6964 │ ACT DR4 Frequency Maps at 98 and 150   │ These FITS files are the maps made     │
│                          │ GHz presented in Aiola et al. 2020     │ with the nighttime 2013(s13) to        │
│                          │                                        │ 2016(s16) data from the ACTPol camera  │
│                          │                                        │ on the ACT telescope at 98(f090) and   │
│                          │                                        │ 150(f150) GHz.                         │
│                          │                                        │                                        │
│                          │                                        │ These maps and their properties are    │
│                          │                                        │ described in Aiola et al. (2020) and   │
│                          │                                        │ Choi et al. (2020)                     │
│                          │                                        │                                        │
│                          │                                        │ #### Naming and products               │
│                          │                                        │                                        │
│                          │                                        │ The maps are released both as 2- or    │
│                          │                                        │ 4-way independet splits, used to       │
│                          │                                        │ compute the power spectra, and as      │
│                          │                                        │ inverse-variance map-space co-added.   │
│                          │                                        │                                        │
│                          │                                        │ ##### Naming convention                │
│                          │                                        │                                        │
│                          │                                        │ `act_{release}_{season}_{patch}_{arra… │
└──────────────────────────┴────────────────────────────────────────┴────────────────────────────────────────┘
```

Caching Products and Collections
--------------------------------

The most common use of `henry` is for caching collections or products for future use. If you
know that tomorrow you want to use a large collection of data which may not be fully
cached for use, you can use `henry` to manage that caching for you.

```bash
henry cache collection 6851be3dc869d741c82d6964
>>> Cached collection 6851be3dc869d741c82d6964 including 60 files
```

Now when I go to use this collection in a workflow, all the core data is there for
me already and I do not need to wait for it to download. If you want the space back,
you can always uncache it:

```bash
henry collection uncache 6851be3dc869d741c82d6964
Uncached collection 6851be3dc869d741c82d6964
```

You can clear all your caches with
```bash
henry cache clear-all
>>> Cleared cache /tmp
```

Readers and Writers
-------------------

Adding and removing readers and writers to collections is simple using the individual
commands:
```bash
henry collection add-reader 6851be3dc869d741c82d6964 test_user
>>> Successfully added test_user to collection 6851be3dc869d741c82d6964 readers.
>>> Added test_user to readers. Collection ID is 6851be3dc869d741c82d6964
```
and...
```bash
henry collection remove-reader 6851be3dc869d741c82d6964 test_user
>>> Successfully removed test_user from collection 6851be3dc869d741c82d6964 readers.
>>> Removed test_user from readers. Collection ID is 6851be3dc869d741c82d6964
```
The same commands exist for writers, and under `henry product`.