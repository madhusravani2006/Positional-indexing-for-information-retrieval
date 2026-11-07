
 POSITIONAL INDEXING 

 Name       : Velicharla Madhu Sravani
 Language   : Kannada
 Dataset    : Kannada Wikipedia dump (knwiki-latest-pages-articles.xml.bz2), 37,100 articles indexed
 Data link  : https://dumps.wikimedia.org/knwiki/latest/knwiki-latest-pages-articles.xml.bz2
 Index link : https://drive.google.com/drive/folders/1NZXdEiKPE-bT9QMWNOPD1XDPsYdFb5Ie?usp=sharing

----------------------------------------------------------------------------
 1. WHAT THIS PROJECT DOES

In this project, I built a POSITIONAL INDEX for a kannada text collection.
For every term of the vocabulary the postings list stores, each document that contains the term and the list of positions that the term occurs in. 
Every term also stores

   DF (Document Frequency)   = number of documents containing the term
   CF (Collection Frequency) = total number of occurrences of the term in the
                               whole collection

Memory design was done as per given critera:

   * MAIN MEMORY      : only the vocabulary  (term -> DF, CF, byte offset, byte length) and a small document table (docID -> title, length) was stored here.
   * SECONDARY MEMORY : the ENTIRE postings list (file postings.txt on disk)

At query time a term's postings are fetched from disk with seek() + read(), so only the postings of the query terms are loaded into memory.
The indexer is of SPIMI style, so the collection itself does not need to fit in memory while indexing.

----------------------------------------------------------------------------
 2. REQUIREMENTS FOR THE RUNNING

Python 3.8 or newer. The standard library is enough to run.

Run the codeline below on WINDOWS POWERSHELL to ensure proper printing of kannada lexicon.

      $env:PYTHONUTF8 = "1"

----------------------------------------------------------------------------
 3. PROCEDURE TO RUN

Open a terminal INSIDE the src folder, then:

 Step 1 - get data (the mentioned method was used in running experiments, other methods were not explored)
   a) Wikipedia dump (this loads a single xml file):

        https://dumps.wikimedia.org/knwiki/latest/knwiki-latest-pages-articles.xml.bz2

 Step 2 - build the index
       python indexer.py --input ..\knwiki.xml.bz2 --out ..\index_out

   Optional: these are used only for visualisation/to test how long they take to run (this was run to ensure that my code worked properly, final run was done on entire dataset)

      --block-size N   positions held in RAM before a block is flushed to disk
                       (default 2,000,000; use a small value to see multi-block merging)
      --limit N        index only the first N documents (handy for quick tests)

 Step 3 - search (two ways)
   Commands:
      python searcher.py lookup <term> [<term> ...]
      python searcher.py phrase "<word1 word2 word3>"
      python searcher.py prox   "<word1 /3 word2>"       (within 3 words, any order)
      python searcher.py bool   "<a AND b>"   |  "<a OR b>"  |  "<a AND NOT b>"
      python searcher.py rare --n 10                     (rare terms + their index)
      python searcher.py stats

   Common options:  --index <dir> (default index_out)   --out <file> (save output)
                    --full (do not truncate long postings)

   NOTE ON KANNADA DISPLAY:
	The kannada font on windows terminal comes out garbled
	Sample of the terminal view:

   [4] <  ಧ   ಯ   , DF=1, CF=1;
    d27697: 229>
   [5] <     , DF=1, CF=1;
    d35157: 335>

   Because of this, results are saved to a UTF-8 text file (--out), where the
   same entries display correctly. Open that file in Notepad or VS Code.

   MANUAL TESTING (no Kannada typing needed):
      1. Open output.txt. It lists terms and their index entries.
      2. Copy any term from output.txt and paste it into the terminal:
            python searcher.py lookup <pasted term> --out result.txt
         Pasting works even though the terminal draws Kannada badly.
      3. Open result.txt to read the result.
      Terms can also be obtained without typing:
            python searcher.py rare --n 10 --out rare.txt

 Step 4 - run the 5 test cases + 10 rare terms

      python run_tests.py --index index_out --out output.txt

   run_tests.py chooses its test terms automatically from the index, so no
   query has to be typed. Running it again on the same index gives the same
   test cases. All results are saved to output.txt (UTF-8).

----------------------------------------------------------------------------
 4. MODULES

 preprocess.py  The preprocessing step used here is tokenization. Normalization is limited to lowercasing and removing zero-width joiners. It keeps letters, 		combining marks and digits (so Kannada/Indic words are not broken); It ignores zero-width joiners (U+200C/U+200D) that occur inside Kannada 		words; all other characters separate words.

 loaders.py     Document readers (streamed one document at a time):
                  - Wikipedia XML dump (.xml/.bz2/.gz): keeps only real articles
                    (namespace 0, no redirects) and removes wiki markup
                    (templates, references, tables, links, html tags).

 indexer.py     This builds the index on disk. 
		(1) tokenizes each document and records positions (starting at 1) in an in-memory block; 
		(2) when the block is full it is written to disk as a sorted block file;
                (3) all blocks are merged (k-way merge) into one postings file while computing DF and CF and the byte offset of each term;
                (4) writes the vocabulary and document table.

 searcher.py    Loads the vocabulary into RAM, reads postings from disk on demand and answers: term lookup, phrase queries, proximity queries, Boolean 			queries (AND/OR/NOT), rare-term listing and statistics.

 run_tests.py   Runs the 5 test cases and the 10 rare-term examples and saves the results to output.txt. Test terms are chosen automatically from the index.             

----------------------------------------------------------------------------
 5. FILES PRODUCED BY THE INDEXER

 postings.txt    THIS FILE IS STORED ON DISC. One line per term, sorted by term: term <TAB> DF <TAB> CF <TAB> doc:pos,pos,pos;doc:pos;...
                 e.g.  example   2   3   12:5,40;87:9

                 meaning: "example" occurs in 2 documents (DF=2), 3 times in total (CF=3): at positions 5 and 40 of document 12 and at position 9 of 			 document 87. Documents are sorted by docID.

 vocabulary.tsv  term <TAB> DF <TAB> CF <TAB> byte_offset <TAB> byte_length This is loaded into RAM; offset/length point to the term's line in
                 postings.txt.

 docs.tsv        docID <TAB> title <TAB> number_of_tokens

----------------------------------------------------------------------------
 6. TEST CASES  (output is saved in output.txt file)
 1. Rare term (occurs once in the whole collection)  -> DF=1, CF=1, one position
 2. Most frequent term (highest CF)                  -> many documents, many positions
 3. Term that is not in the vocabulary               -> reported as not found
 4. Phrase query (two adjacent words)                -> uses the term positions
 5. Proximity query (same two words within 5 words)  -> uses the term positions
 +  10 rare terms with their positional index

----------------------------------------------------------------------------
 7. LIMITATIONS

 * Positions are word offsets counted from 1 in the token stream of a document.
 * No stemming or stop-word removal: Kannada attaches suffixes to words, so a
   query matches only the exact word form.
 * Postings are stored as readable text (no compression) to keep the index easy
   to inspect.
