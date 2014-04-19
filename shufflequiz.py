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
#
#   There's a number of available options.
#   Just call this script with -h option to check them


# TODO: think on allowing concrete weight spec on quiz file

import sys, os
import random
import argparse
#
_QUESTION_MARK = "pregunta"
_DESCRIPTION_MARK = "enunciat"
_ANSWER_MARK = "resposta"
_RST_ANSWER_SEPARATION = "\n\n"
_RST_DESCR_ANSWER_SEPARATION = "-"*4
_RST_QUESTION_SEPARATION = "\n\n"
_RST_QUIZ_SEPARATION = "\n\n"
#
class Answer:
    def __init__(self, is_correct, is_final):
        self.is_correct = is_correct
        self.is_final = is_final
        self.text = ""
        self.weight = 0

    def add_description(self, text):
        self.text += text
        return self

    def set_weight(self, weight):
        self.weight =  weight

    def is_complete(self):
        """ true if it has an unempty text """
        return self.text <> ""

    def postprocess(self):
        """ cleans up the answer text by removing start and end whitespaces """
        self.text = self.text.strip()
        return self

    def __repr__(self):
        return '{ "is_correct":%s, "is_final":%s, "text":"%s" }'%(self.is_correct, self.is_final, self.text)

    def toRST(self, nr, answer_weighted):
        """ converts this answer into rst format.
            Includes weight when answer_weighted """
        rst_weight = "[%.2f] "%self.weight if answer_weighted else ""
        rst_answer_id = compose_answer_id(nr)
        return "%s*%s)* %s"%(rst_weight, rst_answer_id, self.text)

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
        if answer.is_final and self.options.placefinals:
            self.final_answers.append(answer)
        else:
            self.answers.append(answer)
        self.current_answer = answer
        return self

    def get_nr_answers(self):
        """ returns the number of answers already included in this
        question """
        return len(self.answers) + len(self.final_answers)

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
        self.final_answers = []
        self.current_answer = None
        return self

    def postprocess(self):
        """ cleans up the text info by removing start and end whitespaces
            and shuffles answers if required. """
        self.title = self.title.strip()
        self.descr = self.descr.strip()
        self._compute_weights()
        self._shuffle_answers()
        self._postprocess_answers()
        return self

    def _compute_weights(self):
        """ from the number of correct and incorrect recollected answers,
        computes the weight for correct and incorrect answers."""
        answers = self.answers + self.final_answers
        nr_correct_answers = sum( 1 for answer in answers if answer.is_correct )
        nr_incorrect_answers = len(answers) - nr_correct_answers
        correct_weight = 1.0 / nr_correct_answers if nr_correct_answers > 0 else 0
        incorrect_weight = -1.0 / nr_incorrect_answers if nr_incorrect_answers > 0 else 0
        for answer in answers:
            if answer.is_correct:
                answer.set_weight(correct_weight)
            else:
                answer.set_weight(incorrect_weight)

    def _postprocess_answers(self):
        for answer in self.answers + self.final_answers:
            answer.postprocess()

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
        new_question.final_answers = self.final_answers
        return new_question

    def toRST(self, nr, answers_weighted = False):
        """ converts this question to rst format and numbers it with
            nr.
            If answers_weighted, it includes the corresponding
            weight on each answer """
        title = self._rst_compose_title(nr)
        descr = self.descr
        answers = self._rst_compose_answers(answers_weighted)
        return "\n%s\n%s\n\n%s\n\n%s\n"%(title, descr,
                _RST_DESCR_ANSWER_SEPARATION, answers)

    def toEval(self, nr):
        """ extracts evaluation information from this question.
        Returns the list of headers (question_nr.answer_id) and the
        list of weights of each answer """
        all_headers = []
        all_weights = []
        start_nr = 1
        for answer in self.answers + self.final_answers:
            header = '"%s.%s"'%(nr, compose_answer_id(start_nr))
            weight = answer.weight
            start_nr += 1
            all_headers.append(header)
            all_weights.append(weight)
        if self.options.fixavalanswernr:
            for a in range(start_nr, self.options.maxanswers + 1 ):
                header = '"%s.%s"'%(nr, compose_answer_id(a))
                weight = 0
                all_headers.append(header)
                all_weights.append(weight)

        return all_headers, all_weights

    def _rst_compose_title(self, nr):
        """ composes the title in rst format. """
        title = "%s %s: %s"%(_QUESTION_MARK, nr, self.title)
        underline = compose_underline(title)
        return "%s\n%s\n"%(title, underline)

    def _rst_compose_answers(self, answers_weighted):
        """ composes the answer list in rst format.
            In case answers_weighted then it will show the
            corresponding weights for each answer """
        rstanswers = []
        start_nr = 1
        for answer in self.answers + self.final_answers:
            rstanswers.append(answer.toRST(start_nr, answers_weighted))
            start_nr += 1
        return _RST_ANSWER_SEPARATION.join(rstanswers)

    def __repr__(self):
        answers = ",".join([ repr(r) for r in self.answers ])
        return '{ "title": "%s", "descr":"%s", "answers":[%s] }'%(self.title, self.descr, answers)
#
class Quiz:
    def __init__(self, filename, options, questions=None):
        self.filename = filename
        self.options = options
        self.questions = [] if questions == None else questions

    def run(self):
        self._scan_quiz_file()

    def postprocess(self):
        """ performs shuffling and cleaning up on questions """
        self._shuffle_questions()
        for q in self.questions:
            q.postprocess()

    def nr_questions(self):
        """ returns the number of questions in this quiz """
        return len(self.questions)

    def toRST(self, start_nr, answers_weighted=False):
        """ converts quiz to rst format with questions numbered
        from start_nr """
        rstquestions = []
        for question in self.questions:
            rstquestions.append(question.toRST(start_nr,
                answers_weighted))
            start_nr += 1
        return _RST_QUIZ_SEPARATION.join(rstquestions)

    def toEval(self, start_nr):
        """ extracts from this quiz the evaluation information.
        Returns two lists: first one with headers
        (question_nr.answer_id) and weight per answer """
        all_headers = []
        all_weights = []
        for question in self.questions:
            headers, weights = question.toEval(start_nr)
            start_nr += 1
            all_headers += headers
            all_weights += weights
        return all_headers, all_weights

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
            show_scan_error_and_exit(self.filename, nlin, "expected question but another mark found")
        else:
            state = "question"
        return state

    def _scan_title(self, lin, nlin, question):
        """ scans line on state="title"
            updates question and returns a new state, or quits on error """
        state = "title"
        if is_a_question(lin):
            show_scan_error_and_exit(self.filename, nlin, "unexpected start of question")
        elif is_a_description(lin):   # title is done
            if question.has_proper_title():
                state = "description"
            else:
                show_scan_error_and_exit(self.filename, nlin, "question title unset")
        elif is_an_answer(lin):
            show_scan_error_and_exit(self.filename, nlin, "unexpected start of answer")
        elif not is_a_comment(lin):
            question.appendToTitle(lin)
        return state

    def _process_current_answer(self, lin, nlin, question):
        """ processes lin as an answer.
            Updates question or quits on badformed question """
        answer_header = process_answer_mark(lin)
        if answer_header == None:
            show_scan_error_and_exit(self.filename, nlin, "badformed answer header")
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
                show_scan_error_and_exit(self.filename, nlin, "question description unset")
        elif is_a_question(lin):    # previous question had no responses (it is ok)
            if question.has_proper_description():
                self.questions.append(question.clone())
                state = "title"
                question.reset()
            else:
                show_scan_error_and_exit(self.filename, nlin, "question description unset")
        elif is_a_description(lin):    # badformed: more than one description mark
                show_scan_error_and_exit(self.filename, nlin, "too many description marks")
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
                show_scan_error_and_exit(self.filename, nlin, "unfinished answer")
        elif is_an_answer(lin):     # it is a new answer
            if question.get_nr_answers() >= self.options.maxanswers:
                show_scan_error_and_exit(self.filename, nlin, "exceded max nr of answers per question")
            elif question.has_finished_current_answer():
                self._process_current_answer(lin, nlin, question)
            else:
                show_scan_error_and_exit(self.filename, nlin, "unfinished answer")
        elif is_a_description(lin):
            show_scan_error_and_exit(self.filename, nlin, "unexpected description mark")
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
                show_scan_error_and_exit(self.filename, nlin, "end of file reached leaving unfinished question")
#
class QuizSet:
    def __init__(self, options):
        self.options = options
        self.quizes = []

    def run(self):
        for quizfile in self.options.files:
            self._process(quizfile)
        self._postprocess()

    def export(self):
        """ generates output """
        self._export_exam()
        self._export_validation()
        self._export_eval()

    def _export_exam(self):
        with open(self.options.outputfilenames["exam"], "w") as f:
            start_nr = self.options.startnr
            for quiz in self.quizes:
                f.write(quiz.toRST(start_nr))
                f.write(_RST_QUIZ_SEPARATION)
                start_nr += quiz.nr_questions()

    def _export_validation(self):
        with open(self.options.outputfilenames["revision"], "w") as f:
            start_nr = self.options.startnr
            for quiz in self.quizes:
                f.write(quiz.toRST(start_nr, answers_weighted=True))
                f.write(_RST_QUIZ_SEPARATION)
                start_nr += quiz.nr_questions()

    def _export_eval(self):
        all_headers = []
        all_weights = []
        start_nr = self.options.startnr
        for quiz in self.quizes:
            headers, weights = quiz.toEval(start_nr)
            start_nr += quiz.nr_questions()
            all_headers += headers
            all_weights += weights
        char = self.options.csvseparator
        with open(self.options.outputfilenames["eval"], "w") as f:
            f.write(char.join(all_headers))
            f.write("\n")
            f.write(char.join(str(w) for w in all_weights))
            f.write("\n")

    def _process(self, filename):
        """ processes the corresponding quiz """
        quiz = Quiz(filename, self.options)
        quiz.run()
        self.quizes.append(quiz)

    def _postprocess(self):
        """ performs shuffling and clean up """
        if self.options.shufflefiles:
            all_questions = []
            for quiz in self.quizes:
                all_questions += quiz.questions
            only_quiz = Quiz("allfiles", self.options, all_questions)
            self.quizes = [ only_quiz ]
        for quiz in self.quizes:
            quiz.postprocess()
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
    p.add_argument("-f", "--noPlaceFinal", action="store_false",
            help=u"Do not place final answers at the end",
            dest="placefinals", default=True)
    p.add_argument("-m", "--shuffleFiles", dest="shufflefiles",
            help=u"Do shuffle questions amongst files")

    # output options
    p.add_argument("-o", "--outputFilename", action="store",
            help="Set the output filename", dest="outputfile")
    p.add_argument("-r", "--rewriteOutput", action="store_true",
            help="Do not ask when any output file already exists",
            dest="overwrite")

    # other options
    p.add_argument("-s", "--startQuestionNumber", action="store",
            type=int,
            help=u"Start question numbering by this value (default 1)",
            dest="startnr", default=1)
    p.add_argument("-M", "--maxAnswersPerQuestion", action="store",
            type=int,
            help=u"Set the maximum number of answers per question (default 10)",
            dest="maxanswers", default=10)
    p.add_argument("-F", "--fixAvalAnswerNr", action="store_true", 
            help=u"Do fix the number of answers to the maxAnswersPerQuestion on the avaluation output",
            dest="fixavalanswernr")
    p.add_argument("-c", "--csvSeparator", action="store",
            help=u"Set the separator for the csv file with the evaluation information (default ',')",
            dest="csvseparator", default=',')

    return p
#
def exit_if_option_errors(options):
    """ filters option errors and exits if there are any """
    if not options.outputfile:
        show_error_and_exit("Output filename must be set")
    if options.noshuffle:
        if options.shuffleall or options.shufflequestions or options.shuffleanswers or options.shufflefiles:
            show_error_and_exit("Incompatible options")
    if options.maxanswers < 2:
        show_error_and_exit("Maximum number of answers must be at least 2")
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
    filenames = compose_output_filenames(options.outputfile)
    if not options.overwrite:
        exit_if_outputfiles_already_exist(filenames.values())
    options.outputfilenames = filenames
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
def show_scan_error_and_exit(filename, line, msg):
    """ shows an error in scanning the file, then quits """
    show_error_and_exit("file: %s [line: %s] -> %s."%(filename, line, msg), 3)
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
def compose_underline(text, char="-"):
    """ composes an underline for text with char """
    return char * len(text.decode("utf-8"))
#
def compose_answer_id(nr):
    """ returns an answer id from nr """
    return chr(ord("a")+nr-1)
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

