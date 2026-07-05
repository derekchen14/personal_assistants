---
title: "Vector DBs Are Not Needed for RAG"
tags: [rag, retrieval, vector db, wiki, postgres, embeddings, search]
---

## The Vector DB Reflex
The moment someone says RAG, the team reaches for a dedicated vector database like it is a required checkbox. It is not. You are adding a whole new piece of infrastructure to store some embeddings before you have proven you even need approximate nearest neighbor search.

## Postgres Gets You Far
The database you already run can do vector similarity today. With pgvector you get embeddings, filtering, and joins to your real business data in one place, no second system to sync or keep alive. For anything under a few million vectors, a plain Postgres query is fast enough and nobody has to learn a new query language.

## When You Actually Need One
There is a real threshold where a purpose built store earns its spot, and it is higher than most people think. When you are past tens of millions of vectors, need sub millisecond recall, or want fancy quantization and sharding out of the box, a dedicated engine starts to pay off. Until you hit that wall, the reflex is just premature scaling.

## A Pragmatic Stack
Start with Postgres and pgvector, keep your chunks and metadata in normal tables, and write boring SQL. Measure your latency and recall before you add anything, and only reach for a specialized database when the numbers actually force your hand. The best RAG stack is the one you do not have to babysit.