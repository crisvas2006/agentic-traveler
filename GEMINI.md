When creating or updating new features update the README.md file to reflect the changes if they are significant.

Documentation should be concise and explain the relevant parts in the code.

When creating or updating code add or update comments in the code for methods and classes if the code is not self explanatory or the cognitive load is high.

When implementing a new significant feature start by creating a task_template<feature name>.md in a "feature plan" with the steps that you are planned for that feature and the info related to the feature.

Do not remove fields of models without approval

Prioritize integrating libraries and APIs with low code rather than building complex features from scratch.

Do not commit changes automatically.

Write tests for the current task being developed.
Use logging. 

Project structure should be like:
project-root/
    pyproject.toml      # deps, metadata, config for tools
    src/
        agentic-traveler/
            __init__.py
            ...
    tests/
        test_something.py