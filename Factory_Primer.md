---
dest: ./Factory_Primer.pdf
document_title: "Factory Primer - Quick-Response Apparel Manufacturing"
---

# **Factory Primer**
### Everything you need before starting Track 1 or Track 2

> Three minutes. No manufacturing background required.

---

## 1. Quick response, in three paragraphs

Twenty years ago a clothing brand ordered 100,000 units nine months before the season and
hoped. Zara proved you could instead put a small batch in stores, watch what sells for a
week, and reorder the winners within a fortnight. Shein industrialised the idea, and most of
the industry now runs some version of it.

For the factory this changes the shape of the work completely: instead of a dozen huge
orders planned months ahead, there are **hundreds of small orders in the building at once**,
and the most profitable ones — the reorders of whatever is selling — **arrive without
warning and are due in one to two weeks**.

Two consequences drive both tracks. First, nobody can hold the whole picture in their head
any more, so the general manager spends the day asking *"what is actually happening right
now — and can we take this new order?"* — building their co-pilot is **Track 1**. Second,
the factory does not own enough capacity for its peaks, so batches are constantly farmed
out to outside workshops, and *"who should make this?"* has to be answered within the hour
— that is **Track 2**.

---

## 2. The factory

**SweaterCo** makes knitwear for mall brands. Every order follows the same four steps:

```
   KNITTING  →  ASSEMBLY  →  WASHING  →  PACKING
   (machines     (joining      (wash &      (labels, boxes,
    make the      panels into    press)       final check)
    panels)       a garment)
```

That is all the manufacturing knowledge the project needs. The factory works Monday to
Saturday, and every order carries a customer, a piece count, a due date, and its current
stage.

---

## 3. The outside workshops (Track 2)

When the factory is full, batches are sent to one of **eight outside workshops** in the
surrounding region. They differ in ways that matter: one is fast but sloppy, one is
immaculate but tiny, one is cheap but slow. Each has a profile card in `workshops.csv`, and
before any batch can go anywhere, three questions must be answered: **can they make it**
(not everyone is equipped for every product), **can they take it now** (capacity and
current queue), and **are they allowed to** (one is suspended, one is on trial).

Today all three answers live in one dispatcher's head, and the choice is posted in a group
chat with no record of the reasoning. Building the system that answers them instantly — and
proving it allocates better than simple rules — is the whole of Track 2.

---

## 4. The data

Three small, clean CSV files (see `data_dictionary.md` — half a page):

| File | What it is |
|---|---|
| `orders.csv` | 120 orders: who, what, how many, due when, at what stage |
| `production_log.csv` | Daily output per stage for 90 days |
| `workshops.csv` | Profile cards for the 8 outside workshops: what they make, capacity, queue, quality, price, status |

The data is intentionally simple — you can read all of it in a spreadsheet in five minutes.
The hard part of these tracks is the agent and its interface, not the data.

---

## 5. Glossary

| Term | Meaning |
|---|---|
| **Quick response** | Small first runs, then fast reorders of whatever sells |
| **Reorder** | A repeat of a style that is selling — urgent and unplanned |
| **Order** | One job in the factory |
| **Stage** | One of the four steps: knitting, assembly, washing, packing |
| **Batch** | An order (or part of one) sent to a workshop as one unit of work |
| **Workshop / subcontractor** | An outside shop that takes batches when the factory is full |
