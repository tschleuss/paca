@admin @git
Feature: Setting up a Git identity and returning from the platform
  An administrator connects a platform from Administration, Git: the dialog
  collects the optional app name and organization, the platform is asked to
  start the setup, and the browser is sent to the platform. The platform sends
  the browser back to /git/setup/callback, which finishes the setup (or an
  access grant) exactly once and returns the user to where they started.
  Providers and the setup endpoints are stubbed in the browser; the callback
  page is also tried against the real API.

  Background:
    Given the user already has a stored authenticated admin session

  Rule: The setup dialog

    Scenario: Connecting a platform asks for optional details
      Given a provider with no identity
      When the administrator clicks "Set up"
      Then a dialog titled "Set up Example Git on git.example.test" shows "App name (optional)", "Organization (optional)" and the public-app switch

    Scenario: Details are sent to the platform and the browser follows it
      When the administrator enters an app name and an organization, switches on the public app, and continues
      Then the setup request carries the provider, host, name, owner_org and public true
      And the browser is sent to the platform's page

    Scenario: Cancel closes the dialog without calling the platform
      When the administrator cancels
      Then no setup request is made

    Scenario: Removing an identity asks for confirmation
      Given a provider with a shared identity
      When the administrator clicks "Remove"
      Then the dialog "Remove this identity?" explains what happens
      When the administrator confirms with "Remove identity"
      Then the identity is deleted

  Rule: The callback page

    Scenario: A callback without a state is invalid
      When the browser opens /git/setup/callback with no parameters
      Then "Setup could not be completed" and "This setup link is invalid, expired or already used." are shown
      And a link goes back to Git settings

    Scenario: A state the API does not know fails with a message
      When the browser opens /git/setup/callback?state=unknown&code=abc
      Then the failure is shown instead of a blank page

    Scenario: A finished setup returns to Git settings
      Given the API completes the setup
      When the browser opens the callback with a state and code
      Then the code is sent exactly once, with every other query parameter
      And the browser lands on /admin/git

    Scenario: A finished access grant returns to the project
      Given the browser remembers an access flow for a project
      And the API completes the grant with a return url in the project
      Then the browser lands on that project's settings

    Scenario: A return url on another site is ignored
      Given the API answers a return url on another origin
      Then the browser lands on /admin/git

    Scenario: A setup that needs another step sends the browser on
      Given the API answers a next step
      Then the browser follows it
