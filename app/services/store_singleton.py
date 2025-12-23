# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Global job store singleton for dependency injection.

This module provides a centralized location for the global job store instance,
avoiding circular import issues between main.py and routes.py.
"""

from app.services.job_store import JobStore

# Global job store instance
_job_store = JobStore()


def get_job_store() -> JobStore:
    """Get the global job store instance for dependency injection.
    
    This function is used as a FastAPI dependency to provide the global
    job store instance. Tests can override this dependency to provide
    a mock job store.
    
    Returns:
        JobStore: The global job store instance.
    """
    return _job_store
