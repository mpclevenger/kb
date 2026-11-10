---
title: Writing an action item that gets done
section: run
order: 3
---
Action items come from many places: an incident review, the risk register, a project retrospective, an audit or a team review. Most of the ones that stall were written with good intentions. They were too big, too vague, or competing with work the team had already planned. A good action item is small enough to finish, clear enough that anyone can tell when it's done, and planned into the team's real work.

## Is it worth an action item?

An action item takes time from a team that already has a full plan. Before opening one, check that it earns that place.

- **It makes something meaningfully better.** It stops a problem from happening again, reduces a risk, or closes a gap, and you can say what changes when it's done.
- **It matters enough to prioritize.** If the team would be comfortable leaving things as they are, an action item isn't the right tool. Record that decision instead, so it's a choice rather than a forgotten task; see [Choosing how to respond to a risk](/guides/choosing-how-to-respond-to-a-risk/).
- **It isn't ordinary work.** Routine tasks belong in the team's own backlog with everything else.

## What a good action item looks like

- **It describes an outcome, not an activity.** "The nightly load alerts the on-call engineer if it hasn't finished by 6 a.m." can be finished and checked. "Look into monitoring" can't.
- **It has one named owner** who has agreed to it. A team or a role isn't an owner; when everyone owns it, nobody does.
- **It's bite-sized.** It fits within one planning cycle. If it can't, it's a project: split it into milestones, each with its own owner and date.
- **It's achievable with what the team has.** The people, access and budget it needs are available, and any dependency on another team is named and agreed with them.
- **The date comes from the owner.** It's set with the team's current plan in view, not picked to look good.
- **"Done" is defined up front.** It says how anyone will know it's finished, such as a merged change, a working alert or an updated runbook.
- **There's a stopgap if the problem stays open a while.** For example, a daily manual check until the automated one is in place.

## An example

After an outage caused by a nightly data load that failed silently:

A weak version: "Improve monitoring of data loads. Owner: Platform team. Due: Q4."

A stronger version: "Alert the on-call engineer when the nightly load hasn't completed by 6 a.m. Owner: the data platform lead. Due: end of next sprint. Done when: a test failure raises the alert and the runbook says what to do next. Until then: the first person in each morning checks the load status."

The second version can be planned, tracked and closed. The first will most likely still be open after the next outage.

## Breaking down a bigger action

- Start with the first step that can be finished within a few weeks. Early progress keeps an action alive.
- Give each milestone its own outcome, owner and date, so a delay in one part is visible on its own.
- Keep the number of open actions per team small. Ten actions that all slip help less than three that close.

## Keeping it moving

- **Put the work where the team plans.** If the action lives only in a review document or a register, it competes with nothing and loses to everything. Add it to the team's backlog or sprint, linked back to where it came from.
- **Check progress where the team already meets.** A one-line update at the team's regular planning or status meeting is enough.
- **Raise a slip before the date passes.** Give the reason and a realistic new date. A second slip is a signal to rethink the scope, the owner or whether the action is still the right answer, not just to move the date again.
- **Close it with something to show.** Link the change, the alert or the document that proves it's done, so whoever raised it can confirm without a follow-up.

## Before you commit

- Would you prioritize this over something already in your plan?
- Can the owner name the first step and when it will happen?
- Will someone else be able to tell it's done without asking?

If you're unsure, Tech Risk can help.
