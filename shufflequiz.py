#! /usr/bin/python
# encoding: utf-8
#
# File:     shufflequiz.py
# Author:   moises
# Date:     20140418
# Descr:    Process one or more files of quiz format and converts them
#           into rst format

# Input
# -----

# A quiz file has the following format

# . Comments: any line starting with:
#   .. #
#   .. //

# . Questions: a line starting with:
#   .. pregunta:
#   followed by one or more lines with the title of the question
#

# . Description: a line starting with:
#   .. enunciat:
#   followed by one or more lines with the description of the
#   question.
#   Note: the description should follow a question, otherwise an error
#   is issued.

# . Answer: a line starting with:
#   .. resposta: [+-]f?
#   followed by one or more lines with the description of the answer.
#
#   An answer marked as + is considered a correct answer. On the other
#   hand, incorrect answers will be marked as -. Any other mark will
#   issue an error.

#   An answer marked as f (final) will be placed at the end of the
#   list of answers. If more than one answer is marked as final, all
#   them will appear at the end of the list of answers in the same
#   order as they appear in the quiz file. Use this feature for
#   example, to place answers as "All the above are incorrect".

#   Note: the answer should follow a description or another answer,
#   otherwise an error is issued.
#   Also: a question can be wellformed with just a title and a 
#   description, no answers are required.
#
#   Example:

#       .. pregunta:
#       On authors
#       .. enunciat:
#       Who wrote this code?
#       .. resposta: -f
#       None of the above.
#       .. resposta: +
#       It was me!
#       .. resposta: -
#       It was you!

# The previous example could generate the following result

#       Pregunta 5: On authors
#       ----------------------
#
#       Who wrote this code?
#
#       ----
#
#       *a)* It was you!
#
#       *b)* It was me!
#
#       *c)* None of the above.

# Options
# -------
import sys, os
import random
import argparse
#
_QUESTION_MARK = "pregunta"
_DESCRIPTION_MARK = "enunciat"
_ANSWER_MARK = "resposta"
#
class Answer:
    def __init__(self, is_correct, is_final):
        self.is_correct = is_correct
        self.is_final = is_final
        self.text = ""

    def add_description(self, text):
        self.text += text
        return self

    def is_complete(self):
        """ true if it has an unempty text """
        return self.text <> ""

    def postprocess(self):
        """ cleans up the answer text by removing start and end whitespaces """
        self.text = self.text.strip()
        return self

    def __repr__(self):
        return '{ "is_correct":%s, "is_final":%s, "text":"%s" }'%(self.is_correct, self.is_final, self.text)

class Question:
    def __init__(self, options):
        self.options = options
        self.reset()

    def appendToTitle(self, title):
        cleantitle = title.strip()
        if cleantitle <> "":
            self.title += " " + cleantitle
        return self

    def add_description(self, descr):
        self.descr += descr
        return self

    def addAnswer(self, answer):
        self.answers.append(answer)
        self.current_answer = answer
        return self

    def has_proper_title(self):
        """ true if it has proper title """
        return self.title <> ""

    def has_proper_description(self):
        """ true if it has proper description """
        return self.descr <> ""

    def has_finished_current_answer(self):
        """ true if current answer is complete """
        return self.current_answer.is_complete()

    def is_complete(self):
        """ true if it has proper title and description, and
        has finished current answer """
        return self.has_proper_title() and self.has_proper_description() and self.has_finished_current_answer()

    def reset(self):
        """ sets all properties to initial values """
        self.title = ""
        self.descr = ""
        self.answers = []
        self.current_answer = None
        return self

    def postprocess(self):
        """ cleans up the text info by removing start and end whitespaces
            and shuffles answers if required. """
        self.title = self.title.strip()
        self.descr = self.descr.strip()
        self._shuffle_answers()
        for answer in self.answers:
            answer.postprocess()
        return self

    def _shuffle_answers(self):
        """ shuffles answers if required """
        if self.options.shuffleanswers:
            random.shuffle(self.answers)

    def clone(self):
        """ returns a clon of this question.
            It does not clone answers (not required for 
            current usage). It should be done however if
            once cloned, answers could be modified. """
        new_question = Question(self.options)
        new_question.title = self.title
        new_question.descr = self.descr
        new_question.answers = self.answers
        return new_question

    def __repr__(self):
        answers = ",".join([ repr(r) for r in self.answers ])
        return '{ "title": "%s", "descr":"%s", "answers":[%s] }'%(self.title, self.descr, answers)
#
class Quiz:
    def __init__(self, filename, options):
        self.filename = filename
        self.options = options
        self.questions = []

    def run(self):
        self._scan_quiz_file()
        self._shuffle_questions()
        for q in self.questions:
            q.postprocess()

    def _shuffle_questions(self):
        """ shuffles questions if required """
        if self.options.shufflequestions:
            random.shuffle(self.questions)

    def _scan_question(self, lin, nlin, question):
        """ scans line lin on state="question" 
            Returns new state and question, or quits on error """
        if is_a_question(lin):
            state = "title"
            question.reset()
        elif is_a_description(lin) or is_an_answer(lin):
            show_error_and_exit("file: %s [at line: %s] -> expected question but another mark found"%(self.filename, nlin), 3)
        else:
            state = "question"
        return state

    def _scan_title(self, lin, nlin, question):
        """ scans line on state="title"
            updates question and returns a new state, or quits on error """
        state = "title"
        if is_a_question(lin):
            show_error_and_exit("file: %s [at line: %s] -> unexpected start of question"%(self.filename, nlin), 3)
        elif is_a_description(lin):   # title is done
            if question.has_proper_title():
                state = "description"
            else:
                show_error_and_exit("file: %s [at line: %s] -> question title unset"%(self.filename, nlin), 3)
        elif is_an_answer(lin):
            show_error_and_exit("file: %s [at line: %s] -> unexpected start of answer"%(self.filename, nlin), 3)
        elif not is_a_comment(lin):
            question.appendToTitle(lin)
        return state

    def _process_current_answer(self, lin, nlin, question):
        """ processes lin as an answer.
            Updates question or quits on badformed question """
        answer_header = process_answer_mark(lin)
        if answer_header == None:
            show_error_and_exit("file: %s [at line: %s] -> badformed answer header"%(self.filename, nlin), 3)
        else:
            is_correct, is_final = answer_header
            partial_answer = Answer(is_correct, is_final)
            question.addAnswer(partial_answer)

    def _scan_description(self, lin, nlin, question):
        """ scans line on state="description"
            updates question and returns a new state, or quits on error """
        state = "description"
        if is_an_answer(lin):      # description is over
            if question.has_proper_description():
                self._process_current_answer(lin, nlin, question)
                state = "answer"
            else:
                show_error_and_exit("file: %s [at line: %s] -> question description unset"%(self.filename, nlin), 3)
        elif is_a_question(lin):    # previous question had no responses (it is ok)
            if question.has_proper_description():
                self.questions.append(question.clone())
                state = "title"
                question.reset()
            else:
                show_error_and_exit("file: %s [at line: %s] -> question description unset"%(self.filename, nlin), 3)
        elif is_a_description(lin):    # badformed: more than one description mark
                show_error_and_exit("file: %s [at line: %s] -> too many description marks"%(self.filename, nlin), 3)
        elif not is_a_comment(lin):
            question.add_description(lin)
        return state

    def _scan_answer(self, lin, nlin, question):
        """ scans line on state="description"
            updates question and returns a new state, or quits on error """
        state = "answer"
        if is_a_question(lin):  # end of answers, new question
            if question.has_finished_current_answer():
                self.questions.append(question.clone())
                question.reset()
                state = "title"
            else:
                show_error_and_exit("file: %s [at line: %s] -> unfinished answer"%(self.filename, nlin), 3)
        elif is_an_answer(lin):     # it is a new answer
            if question.has_finished_current_answer():
                self._process_current_answer(lin, nlin, question)
            else:
                show_error_and_exit("file: %s [at line: %s] -> unfinished answer"%(self.filename, nlin), 3)
        elif is_a_description(lin):
            show_error_and_exit("file: %s [at line: %s] -> unexpected description mark"%(self.filename, nlin), 3)
        elif not is_a_comment(lin):
            question.current_answer.add_description(lin)
        return state

    def _scan_quiz_file(self):
        """ interprets quiz filename and place corresponding questions on
        self.questions.
        It works as an state machine with the following states:

            - question:     waiting to get a question mark
            - title:        waiting to get a title
            - description:  waiting to get a description
            - answer:       waiting to get the text of an answer
        """
        state = "question"
        nlin = 0            # line number under process
        question = Question(self.options)

        with open(self.filename) as f:
            for lin in f:
                nlin += 1
                if is_a_comment(lin):
                    pass
                elif state == "question":
                    state = self._scan_question(lin, nlin, question)
                elif state == "title":
                    state = self._scan_title(lin, nlin, question)
                elif state == "description":
                    state = self._scan_description(lin, nlin, question)
                elif state == "answer":
                    state = self._scan_answer(lin, nlin, question)
            # check last question
            if question.is_complete():
                self.questions.append(question) # it is not required to clone
            else:
                show_error_and_exit("file: %s [at line: %s] -> end of file reached leaving unfinished question"%(self.filename, nlin), 3)
#
class QuizSet:
    def __init__(self, options):
        self.options = options
        self.questions = []  # list of questions

    def run(self):
        self._shuffle_inputfiles()
        for quizfile in self.options.files:
            self._process(quizfile)

    def export(self):
        """ generates output """
        self._export_exam()
        self._export_validation()
        self._export_eval()

    def _export_exam(self):
        print "XXX HERE AM I!"
    def _export_validation(self):
        print "XXX HERE AM I!"
    def _export_eval(self):
        print "XXX HERE AM I!"

    def _process(self, filename):
        """ processes the corresponding quiz """
        quiz = Quiz(filename, self.options)
        quiz.run()

    def _shuffle_inputfiles(self):
        """ shuffle input files if required """
        if self.options.shufflefiles:
            random.shuffle(self.options.files)
#
def compose_argparse():
    """ composes and returns an ArgumentParser """
    p = argparse.ArgumentParser(description = "Quiz shuffler", version="1.0")

    p.add_argument('files', metavar='quizfiles', nargs='+', help="quiz files file paths with .quiz extension")

    # shuffle options
    p.add_argument("-e", "--shuffleAll", action="store_true",
            help=u"Do shuffle questions and answers", dest="shuffleall")
    p.add_argument("-n", "--noShuffle",  action="store_true", 
            help=u"Do not shuffle anything, not even final questions",
            dest="noshuffle")
    p.add_argument("-q", "--shuffleQuestions", action="store_true", 
            help=u"Do shuffle questions", dest="shufflequestions")
    p.add_argument("-a", "--shuffleAnswers", action="store_true", 
            help=u"Do shuffle questions and answers", dest="shuffleanswers")
    p.add_argument("-f", "--placeFinal", action="store_true",
            help=u"Do place final answers at the end (default)",
            dest="placefinals", default=True)
    p.add_argument("-m", "--shuffleFiles", dest="shufflefiles",
            help=u"Do shuffle questions amongst files")

    # output options
    p.add_argument("-o", "--outputFilename", action="store",
            help="Set the output filename", dest="outputfilename")
    p.add_argument("-r", "--rewriteOutput", action="store_true",
            help="Do not ask when any output file already exists",
            dest="overwrite")
    return p
#
def exit_if_option_errors(options):
    """ filters option errors and exits if there are any """
    if not options.outputfilename:
        show_error_and_exit("Output filename must be set")
    if options.noshuffle:
        if options.shuffleall or options.shufflequestions or options.shuffleanswers or options.shufflefiles:
            show_error_and_exit("Incompatible options")
    for fn in options.files:
        if not fn.endswith(".quiz"):
            show_error_and_exit("Input files must have .quiz extension")
#
def expand_options(options):
    """ some options implie others (e.g. shuffleAll implies
    shuffleQuestions and shuffleAnswers) This function just cascades
    them """
    options.shuffleanswers = options.shuffleanswers or options.shuffleall
    options.shufflequestions = options.shufflequestions or options.shuffleall
    options.shufflefiles = options.shufflefiles or options.shuffleall
    options.shufflequestions = options.shufflequestions or options.shufflefiles
#
def compose_output_filenames_and_exit_if_no_overwrite(options):
    """ composes output filenames and check whether they already exist
    and overwrite option hasn't been set.
    If everything is ok, it adds outputfilenames to options """
    filenames = compose_output_filenames(options.outputfilename)
    if not options.overwrite:
        exit_if_outputfiles_already_exist(filenames.values())
    options.outputfilename = filenames
#
def get_options():
    """ returns the call arguments as an optparse """
    p = compose_argparse()
    options = p.parse_args()
    exit_if_option_errors(options)
    exit_if_inputfiles_do_not_exist(options.files)
    compose_output_filenames_and_exit_if_no_overwrite(options)
    expand_options(options)
    return options
#
def compose_output_filenames(filename):
    """ composes and returns the output filenames from filename.
        It returns a dict with { "exam":"«filename».rst",
        "revision":«filename».rev.rst", "eval":"«filename».eval.csv
        """
    basename, ext = os.path.splitext(filename)
    outputfilename = filename if ext == ".rst" else "%s.rst"%basename
    filenames = { 
            "exam": outputfilename, 
            "revision":
            "%s.rev.rst"%basename, 
            "eval":"%s.eval.csv"%basename
            }
    return filenames
#
def show_error_and_exit(msg, exit_code=1):
    """ shows an error missage and exists with exit_code """
    print >> sys.stderr, "%s: error: %s"%(sys.argv[0], msg)
    sys.exit(exit_code)
#

def existing_files(filenames):
    """ returns the list of existing files """
    return [ f for f in filenames if os.path.isfile(f)]
#
def missing_files(filenames):
    """ returns the list of missing files """
    return [ f for f in filenames if not os.path.isfile(f)]
#
def exit_if_outputfiles_already_exist(filenames):
    """ check if any of the filenames already exists.
    In this case, it issues an error and finishes execution """
    existing = existing_files(filenames)
    if existing <> []:
        show_error_and_exit("Output file %s already exists. Remove it or use --rewriteOutput option"%existing[0], 2);
#
def exit_if_inputfiles_do_not_exist(filenames):
    """ check if any of the filenames doesn't exists """
    missing = missing_files(filenames)
    if missing <> [] :
        show_error_and_exit("Input file %s doesn't exist"%missing[0], 2);
#
def is_a_comment(lin):
    """ true if lin is a comment """
    return lin.startswith(".. #") or lin.startswith(".. /")

def is_a_question(lin):
    """ true if lin is the start of a question """
    return lin.startswith(".. %s:"%_QUESTION_MARK)
#
def is_a_description(lin):
    """ true if lin is the start of a question """
    return lin.startswith(".. %s:"%_DESCRIPTION_MARK)
#
def is_an_answer(lin):
    """ true if lin is the start of a answer """
    return lin.startswith(".. %s:"%_ANSWER_MARK)
#
def process_answer_mark(lin):
    """ it lin is an answer, it returns whether it is 
    marked as correct and/or final. It returns None if
    lin is not an answer or is not well formed """
    res = None
    if is_an_answer(lin):
        line = lin.rstrip()
        if line.endswith('f'):
            final = True
            value = line[-2:-1]
        else:
            final = False
            value = line[-1:]

        if value in ('+', '-'):
            correct = (value == '+')
            res = (correct, final)
    return res

#
def main():
    options = get_options()
    quiz_set = QuizSet(options)
    quiz_set.run()
    quiz_set.export()
#
if __name__=="__main__":
    sys.exit(main())

