"""Explicit edition extension points. Community has no hosted imports or dependencies."""


class LocalRuntime:
    def public_record(self, obj, data):
        return data

    def retry_operation(self, previous):
        pass

    def queued(self, session, job, meeting):
        pass

    def cancelled(self, session, job):
        pass

    def checkpointed(self, session, job):
        pass

    def analysis_options(self, options):
        return options

    def analysis_data(self, job, data):
        return data

    def analysis_allowed(self, data):
        from . import auth

        if data["provider"] == "chatgpt":
            auth.token()

    def artifacts_ready(self, job_id):
        pass

    def before_complete(self, session, job):
        pass

    def capabilities(self):
        return {
            "edition": "local",
            "role": "owner",
            "edit_criteria": True,
            "review_criteria": True,
            "subscription_required": False,
        }


runtime = LocalRuntime()


def install(implementation):
    global runtime
    runtime = implementation
