@projects @git
Feature: A project's Git settings
  The Git tab of a project's settings links repositories and sets the
  automation. Reading it needs git:read. Linking a repository needs git:write
  on the project and the workspace-level git.identities:manage; a writer
  without it is told who to ask instead of being shown a form that would fail.
  The e2e stack has no Git provider plugin, so the provider endpoints are
  stubbed in the browser.

  Rule: The tab reflects what is installed

    Background:
      Given the user already has a stored authenticated admin session
      And a project

    Scenario: No provider is installed
      Given the platform lists no Git provider
      When the user opens the project's Git settings
      Then the page says no Git provider is installed
      And it offers a button to open the Git integration

    Scenario: An administrator links a repository
      Given the platform lists a Git provider and the project has no repository
      When the user opens the project's Git settings
      Then the "Repository" field and the "Link" button are shown
      When the user types "acme/web" and clicks "Link"
      Then the request names the provider and the typed path
      And "acme/web" is listed under Repositories

  Rule: Who sees the link form

    Background:
      Given the user already has a stored authenticated admin session
      And a project
      And the platform lists a Git provider and the project has no repository

    Scenario: A writer without git.identities:manage is told to ask an administrator
      Given a member with "git:read" and "git:write" and no workspace role
      When the member opens the project's Git settings
      Then the page explains that linking also needs the workspace permission to manage Git identities
      And there is no "Link" button

    Scenario: A writer with git.identities:manage gets the form
      Given a member with "git:read" and "git:write" and the workspace action "git.identities:manage"
      When the member opens the project's Git settings
      Then the "Repository" field and the "Link" button are shown

    Scenario: A reader is told they need write access
      Given a member with only "git:read"
      When the member opens the project's Git settings
      Then the page says Git write access is needed to link repositories
      And there is no "Link" button
