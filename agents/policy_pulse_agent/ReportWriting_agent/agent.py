# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from google.adk.agents import Agent
from policy_pulse_agent.agent import RetrieveContextTool

INSTRUCTION = (
        "You are a time information agent."
        "You will help provide the user with the current local time in a specified city."
        "The following tool will help you with answering the requests:"
        " - get_current_time(): use this to get the current local time for any city."
        ""
        "If the user's request is incomplete, ask for the city."
        "In case the city is unsupported, give a regret response."
    )

ReportWriting_agent = Agent(
    name="ReportWriting_agent",
    model="gemini-2.5-flash-preview-05-20",
    description=(
        "Agent which long-form and research type writing in prder to draft reports, policies etc."
    ),
    instruction=INSTRUCTION,
    tools=[RetrieveContextTool]
)