@admin @git
Feature: Administration, Git
  The Git page lists the platforms the installed provider plugins support and
  whether each has a shared bot identity. It is for holders of the workspace
  action git.identities:manage; everyone else is sent home and does not see the
  entry in the sidebar. The e2e stack has no Git provider plugin, so the
  provider and identity endpoints are stubbed in the browser.

  Rule: What the page shows

    Background:
      Given the user already has a stored authenticated admin session

    Scenario: No provider plugin is installed
      Given the platform lists no Git provider
      When the user opens Administration, Git
      Then the page says no Git provider is installed
      And it links to the plugins page

    Scenario: A platform without an identity is not connected
      Given the platform lists a Git provider and no identity
      When the user opens Administration, Git
      Then the platform's card is "Not connected" and offers "Set up"

    Scenario: A platform with an identity shows the bot to mention
      Given the platform lists a Git provider and a shared identity "paca-bot"
      When the user opens Administration, Git
      Then the platform's card is "Connected" and shows "@paca-bot"
      And it offers "Remove"

  Rule: Who may open it

    Scenario: A user without git.identities:manage is sent home
      Given a user with a workspace role that lacks "git.identities:manage"
      When the user opens /admin/git
      Then they land on the home page
      And the sidebar has no Git entry

    Scenario: A holder of git.identities:manage sees the entry and the page
      Given a user with a workspace role granting only "git.identities:manage"
      When the user opens /admin/git
      Then the Git page is shown
