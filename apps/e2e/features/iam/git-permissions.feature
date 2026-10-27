@iam @git
Feature: Who may use the Git integration
  Git access is four project actions (git:read, git:write, git:approve,
  git:merge) and one workspace action (git.identities:manage) for the bot
  identities. Every route is gated in the router. Linking a repository needs
  both git:write on the project and git.identities:manage, because the shared
  identity's installations are instance-wide. The webhook intake is public: the
  Git platform calls it and the provider plugin verifies the signature.

  Rule: Reading and writing a project's Git integration

    Background:
      Given the user already has a stored authenticated admin session
      And a project

    Scenario: A caller who is not signed in is refused
      Then the project's Git routes answer 401 without credentials

    Scenario: A signed-in user with no role on the project is refused
      Then the project's Git routes answer 403

    Scenario: git:read reads and cannot change anything
      Given a member whose project role grants only "git:read"
      Then listing providers, repositories, runs and settings answers 200
      But changing settings, linking, requesting access and minting a write credential answer 403

    Scenario: A role on another project grants nothing here
      Given a member whose "git:write" role belongs to a different project
      Then the project's Git routes answer 403

  Rule: Linking a repository

    Background:
      Given the user already has a stored authenticated admin session
      And a project

    Scenario: git:write alone cannot link a repository
      Given a member whose project role grants "git:write"
      Then linking a repository answers 403
      But saving the project's Git settings is not refused

    Scenario: git.identities:manage alone cannot link a repository
      Given a user with the workspace action "git.identities:manage" and no role on the project
      Then linking a repository answers 403

    Scenario: git:write together with git.identities:manage passes the gate
      Given a member with "git:write" on the project and "git.identities:manage" in the workspace
      Then linking a repository is not refused for permissions

  Rule: Approving and merging are their own actions

    Background:
      Given the user already has a stored authenticated admin session
      And a project

    Scenario: git:write cannot approve or merge
      Given a member whose project role grants "git:read" and "git:write"
      Then approving and merging a change request answer 403

    Scenario: git:approve and git:merge each open only their own route
      Given a member whose project role grants only "git:approve"
      Then approving is not refused for permissions but merging answers 403
      Given a member whose project role grants only "git:merge"
      Then merging is not refused for permissions but approving answers 403

  Rule: Bot identities are a workspace privilege

    Background:
      Given the user already has a stored authenticated admin session

    Scenario: Listing providers and identities needs git.identities:manage
      Given a user with the workspace action "git.identities:manage"
      Then GET /git/providers and GET /git/identities answer 200
      Given a user with a workspace role granting only "git:*"
      Then both answer 403

    Scenario: A project role cannot reach the workspace routes
      Given a member whose project role grants "git:*"
      Then GET /git/identities, setting up an identity and removing one answer 403

  Rule: The webhook intake is public

    Scenario: An unknown endpoint key is a 404, not a 401
      When a platform posts to /git/webhooks/<unknown key> without credentials
      Then the answer is 404
