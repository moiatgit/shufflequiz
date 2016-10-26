#! /usr/bin/python
# encoding: utf-8
#
# File:     quiz2moodlexml.py
# Author:   moises
# Date:     20151202
# Descr:    Process one or more files of quiz format and converts them
#           into moodle xml format

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

#   Answers marked as f (final) will be considered as regular answers since Moodle can't represent
#   them as final.

#   All the text, except for question titles, can be markdown formatted

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
#       None of the rest.
#       .. resposta: +
#       It was me!
#       .. resposta: -
#       It was you!

# The previous example would generate the following result

#    <question type="multichoice">
#        <name>
#            <text>On authors</text>
#        </name>
#        <questiontext format="markdown">
#            <text>
#                <![CDATA[
#    Who wrote this code?
#                ]]>
#            </text>
#        </questiontext>
#        <single>false</single>
#        <shuffleanswers>true</shuffleanswers>
#
#        <answer fraction="-50" format="markdown">
#            <text><![CDATA[
#    None of the rest.
#                ]]></text>
#        </answer>
#
#        <answer fraction="100" format="markdown">
#            <text><![CDATA[
#    It was me!
#                ]]></text>
#        </answer>
#
#        <answer fraction="-50" format="markdown">
#            <text><![CDATA[
#    It was you!
#                ]]></text>
#        </answer>
#
#    </question>
#

# Options
# -------
#
#   There's a number of available options.
#   Just call this script with -h option to check them

# TODO: check quiz file for param .. markdown: md or markup. Otherwise it might not work for moodle
# TODO: change 'Preguntes guais' by something in args

import sys, os
import random
import argparse
import re
import datetime
#
_QUESTION_MARK = "pregunta"
_DESCRIPTION_MARK = "enunciat"
_ANSWER_MARK = "resposta"

_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>

<!-- 
     This file has been generated automaticaly using %s
     from file/s: %s
     on date: %s 
-->

<quiz>
<!-- question: 0  -->
  <question type="category">
      <category>
          <text>$course$/Preguntes guais</text>
      </category>
  </question>
%s
</quiz>
"""     # it requires some parameters

_XML_QUESTION_TEMPLATE = """
    <question type="multichoice">
        <name>
            <text>%s</text>
        </name>
        <questiontext format="markdown">
            <text>
                <![CDATA[%s]]>
            </text>
        </questiontext>
        <single>false</single>
        <shuffleanswers>true</shuffleanswers>
%s
    </question>
"""     # it requires (title, description, answers)

_XML_ANSWER_TEMPLATE = """
        <answer fraction="%s" format="markdown">
            <text><![CDATA[
                %s
                ]]></text>
        </answer>
"""     # it requires (weight, description)

_XML_QUIZ_SEPARATION = "\n\n\n"     # TODO: consider adding a comment of the quiz filename
_XML_QUESTION_SEPARATION = "\n\n\n"
_XML_ANSWER_SEPARATION = "\n"


#
_QUESTION_TITLE = "Pregunta"
#
_MAP_GIFT_WEIGHTS = { # weights from nr of answers of the same category
    1:"100",
    2:"50",
    3:"33.33333",
    4:"25",
    5:"20",
    6:"16.66667",
    7:"14.28571",
    8:"12.5",
    9:"11.11111",
    10:"10",
    -10:"-10",
    -9:"-11.11111",
    -8:"-12.5",
    -7:"-14.28571",
    -6:"-16.66667",
    -5:"-20",
    -4:"-25",
    -3:"-33.33333",
    -2:"-50",
    -1:"-100" 
}

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
        """ cleans up the answer text by:
            a) removing start and end whitespaces
            b) adding a new line at the begining when it starts with a
            comment or rst directive (btw: a comment matches "^\s*\.\..*" )
        """
        self.text = self.text.strip()
        if re.match("^\s*\.\..*", self.text):
            self.text = os.linesep * 2 + self.text
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

    def add_answer(self, answer):
        self.answers.append(answer)
        self.current_answer = answer
        if answer.is_correct:
            self.nr_correct_answers += 1
        else:
            self.nr_incorrect_answers += 1
        return self

    def get_nr_answers(self):
        """ returns the number of answers already included in this question """
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
        self.nr_correct_answers = 0
        self.nr_incorrect_answers = 0
        return self

    def postprocess(self):
        """ cleans up the text info by removing start and end whitespaces
            and shuffles answers if required. """
        self.title = self.title.strip()
        self.descr = self.descr.strip()
        self._postprocess_answers()
        return self

    def _postprocess_answers(self):
        for answer in self.answers:
            answer.postprocess()

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
        new_question.nr_correct_answers = self.nr_correct_answers
        new_question.nr_incorrect_answers = self.nr_incorrect_answers
        return new_question

    def toXML(self):
        """ extracts evaluation information from this question in Moodle XML format """
        xmlanswers = self._xml_composeanswers()
        return _XML_QUESTION_TEMPLATE%(self.title, self.descr, xmlanswers)

    def _rst_compose_title(self, nr):
        """ composes the title in rst format. """
        title = "%s %s: %s"%(_QUESTION_TITLE, nr, self.title)
        underline = compose_underline(title)
        return "%s\n%s\n"%(title, underline)

    def _compute_answer_class(self, is_correct):
        """ returns the number of answers in the class. 
        The possible classes are: correct and incorrect answers.
        This is a helping function to compute the weight of an answer.
        When class is incorrect, the value return is negative. """
        nr_correct = self.nr_correct_answers
        return self.nr_correct_answers if is_correct else -self.nr_incorrect_answers

    def _compute_answer_weight_fulldecimal(self, is_correct):
        """ computes and returns the weight of an answer when there are
        as many as nr of its class. """
        return 1.0 / self._compute_answer_class(is_correct)

    def _xml_composeanswers(self):
        """ composes the evaluation information of the answer list in gift format."""
        xmlanswers = []
        for answer in self.answers:
            answer_weight = self._compute_answer_weight_for_gift(answer.is_correct)
            xmlanswer = _XML_ANSWER_TEMPLATE%(answer_weight, answer.text)
            xmlanswers.append(xmlanswer)
        return _XML_ANSWER_SEPARATION.join(xmlanswers)

    def _compute_answer_weight_for_gift(self, is_correct):
        """ returns the weight of an answer deppending on whether is_correct or not.
        The result is a string with the format expected by Moodle's Gift """
        nr = self._compute_answer_class(is_correct)
        weight = _MAP_GIFT_WEIGHTS.get(nr, "%0.3f"%self._compute_answer_weight_fulldecimal(is_correct))
        return weight

    def __repr__(self):
        answers = ",".join([ repr(r) for r in self.answers ])
        return '{ "title": "%s", "descr":"%s", "answers":[%s], "nr_correct":%s }'%(self.title, self.descr, answers, self.nr_correct_answers)
#
class Quiz:
    def __init__(self, filename, options, questions=None):
        self.filename = filename
        self.options = options
        self.questions = [] if questions == None else questions

    def run(self):
        self._scan_quiz_file()

    def postprocess(self):
        """ performs cleaning up on questions """
        for q in self.questions:
            q.postprocess()

    def nr_questions(self):
        """ returns the number of questions in this quiz """
        return len(self.questions)

    def toXML(self):
        """ extracts evaluation information of this quiz in Moodle XML format"""
        return _XML_QUESTION_SEPARATION.join(question.toXML() for question in self.questions)

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
            question.add_answer(partial_answer)

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
        self._export_xml()

    def _export_xml(self):
        xmlquestions = _XML_QUIZ_SEPARATION.join(quiz.toXML() for quiz in self.quizes)

        programname = sys.argv[0]
        fromfiles = ", ".join(self.options.files)
        ondate = datetime.datetime.now().isoformat()
        xmlcontents = _XML_TEMPLATE%(programname, fromfiles, ondate, xmlquestions)
        with open(self.options.outputfilenames["xml"], "w") as f:
            f.write(xmlcontents)

    def _process(self, filename):
        """ processes the corresponding quiz """
        quiz = Quiz(filename, self.options)
        quiz.run()
        self.quizes.append(quiz)

    def _postprocess(self):
        """ performs clean up """
        for quiz in self.quizes:
            quiz.postprocess()
#
def compose_argparse():
    """ composes and returns an ArgumentParser """
    p = argparse.ArgumentParser(description = "Quiz to Moodle XML format converter", version="1.0")

    p.add_argument('files', metavar='quizfiles', nargs='+', help="quiz files file paths with .quiz extension")

    # output options
    p.add_argument("-o", "--outputFilename", action="store",
            help="Set the output filename", dest="outputfile")
    p.add_argument("-r", "--rewriteOutput", action="store_true",
            help="Do not ask when any output file already exists",
            dest="overwrite")

    # other options
    p.add_argument("-M", "--maxAnswersPerQuestion", action="store",
            type=int,
            help=u"Set the maximum number of answers per question (default 10)",
            dest="maxanswers", default=10)
    p.add_argument("-F", "--fixAvalAnswerNr", action="store_true", 
            help=u"Do fix the number of answers to the maxAnswersPerQuestion on the avaluation output",
            dest="fixavalanswernr")

    return p
#
def exit_if_option_errors(options):
    """ filters option errors and exits if there are any """
    if not options.outputfile:
        show_error_and_exit("Output filename must be set")
    if options.maxanswers < 2:
        show_error_and_exit("Maximum number of answers must be at least 2")
    for fn in options.files:
        if not fn.endswith(".quiz"):
            show_error_and_exit("Input files must have .quiz extension")
#
def expand_options(options):
    """ some options implie others (not in this version) This function just cascades
    them """
    pass
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
    """ returns the call arguments as an argparse """
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
        It returns a dict with { "xml":"«filename».xml" }
    """
    basename, ext = os.path.splitext(filename)
    filenames = { 
            "xml": "%s.xml"%basename
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

