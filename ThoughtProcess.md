#Initial Impressions
I thought this task was the coolest from the beginning, however I was quite hesitant to pick it up since I did not know much about running LLMS either locally or OpenAI api calls.

However, after finishing SER I decided to attempt this since it seemed very interesting. However I faced several issues from the start, since local LLMS such as llama3.1 did not obey instructions, often making up random data or facts and deviating from facts.

I finally settled on online APIs but also faced several issues because they kept returning error messages and running to rate limits. Finally, I began work on the project after finally settling on a model and api.

I began with just getting the basic loop of the suspect and interrogator running, with the reasoner just a placeholder. Once the loop was working, I began to think of a way to parse the suspect output and pass it to the reasoner to run consistency checks.
I settled on Pydantic and forced the model to output a Json schema with a list of claims made by the suspect, with several keys such as "time", "location" etc.

I then began implementing consistency checks in the reasoner.py, focusing on time overlap, and if one agent falsely claimed that he had seen another etc. The reasoner has update_case method, which updates the alibi ledgers and contradictions as suspects answer questions.

Finally, although I wasnt quite happy, due to time constraints I finally wrote the architect.py, which compiles the investigation into a final case file. The entire interrogation log, contradictions and alibi info is passed to the LLM to produce a final human readable case report.

Although I couldnt finish the project, since the API kept rate limiting me so I couldnt run large parts of the dataset while local LLMS were too slow, along with the  time constraints, it was definitely very cool and I would love to revisit this later.

