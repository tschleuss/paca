package gitdom

import "errors"

var (
	// ErrNotFound means the repository, identity, endpoint or change request does not exist.
	ErrNotFound = errors.New("git: not found")
	// ErrAlreadyLinked means the project already linked this repository.
	ErrAlreadyLinked = errors.New("git: repository is already linked to this project")
	// ErrNoIdentity means no identity can act on the repository (the platform is not set up for it).
	ErrNoIdentity = errors.New("git: no identity is available for this repository")
	// ErrProviderUnavailable means the provider plugin is not installed, enabled or answering.
	ErrProviderUnavailable = errors.New("git: provider is unavailable")
	// ErrInvalidSignature means a webhook delivery failed verification.
	ErrInvalidSignature = errors.New("git: webhook signature is invalid")
	// ErrUnsupported means the provider does not offer this operation (its capability flag is off).
	ErrUnsupported = errors.New("git: the provider does not support this operation")
	// ErrRateLimited means core refused the call to protect the platform or the repository.
	ErrRateLimited = errors.New("git: rate limited")
	// ErrInvalidInput means the request is malformed in a way only core can tell.
	ErrInvalidInput = errors.New("git: invalid request")
	// ErrRunActive means the agent already has an unfinished run on the subject.
	ErrRunActive = errors.New("git: the agent already has an unfinished run on this subject")
	// ErrIdentityExists means the host already has a shared identity.
	ErrIdentityExists = errors.New("git: a shared identity already exists for this host")
)

var (
	// ErrSetupExpired means the setup state is unknown, expired, already used or belongs to another user.
	// One error for all of them: a caller learns nothing about which.
	ErrSetupExpired = errors.New("git: setup session is invalid or expired")
	// ErrPublicURLRequired means webhooks and redirects need the instance's public URL.
	ErrPublicURLRequired = errors.New("git: PUBLIC_URL is not configured")
	// ErrInvalidReturnURL means the return URL is not on this instance.
	ErrInvalidReturnURL = errors.New("git: return_url must be on this instance")
	// ErrAccessNotGranted means the identity cannot see the repository, and the
	// provider lets a user grant it access to the owner's account.
	ErrAccessNotGranted = errors.New("git: the identity has no access to this repository's owner")
)
