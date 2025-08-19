import { ArkMethod, Scene, Stmt, ViewTreeNode } from "../../../../arkanalyzer/src";
import { PageTransitionGraph, PTGNode } from "../../PageTransitionGraph";

export interface EdgeBuilderInterface{
    scene:Scene;
    ptg:PageTransitionGraph;
    edgeBuilderStrategy: string;
    identifyPTGEdge(ptgNode: PTGNode, method: ArkMethod): void;
}